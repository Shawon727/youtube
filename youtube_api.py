"""YouTube streams — multi-backend, always-on (Piped race + Invidious + yt-dlp)."""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Dict, List, Optional

import httpx

from cookie_manager import CookieManager

try:
    import yt_dlp
except ImportError:
    yt_dlp = None  # type: ignore

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Large static pool — unhealthy ones fail fast in parallel race
PIPED_POOL = [
    "https://pipedapi.ducks.party",
    "https://api.piped.private.coffee",
    "https://pipedapi.adminforge.de",
    "https://pipedapi.reallyaweso.me",
    "https://pipedapi.leptons.xyz",
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.r4fo.com",
    "https://pipedapi.syncpundit.io",
    "https://api-piped.mideva.live",
    "https://pipedapi.drgns.space",
    "https://piped-api.privacy.com.de",
    "https://pipedapi.smnz.de",
    "https://pipedapi.ouo.au",
    "https://pipedapi.tokhmi.xyz",
    "https://api.piped.projectsegfau.lt",
]

INVIDIOUS_POOL = [
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://yewtu.be",
    "https://invidious.flokinet.to",
    "https://iv.ggtyler.dev",
    "https://invidious.materialio.us",
    "https://invidious.protokolla.fi",
    "https://vid.puffyan.us",
    "https://invidious.privacyredirect.com",
]

# Prefer last-success instance first
_prefer_piped: Optional[str] = None
_prefer_inv: Optional[str] = None
_prefer_lock = asyncio.Lock() if False else None  # set at runtime


def extract_id(raw: str) -> str:
    s = (raw or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{6,20}", s):
        return s
    m = re.search(r"(?:v=|/shorts/|youtu\.be/|embed/|live/)([A-Za-z0-9_-]{6,20})", s)
    return m.group(1) if m else s


class YouTubeAPI:
    def __init__(self) -> None:
        self.cookies = CookieManager()
        self._prefer_piped: Optional[str] = None
        self._prefer_inv: Optional[str] = None

    def reload_cookies(self) -> None:
        pass

    async def _run(self, fn, *a, **kw):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: fn(*a, **kw))

    def _client(self, timeout: float = 14.0) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=6.0),
            follow_redirects=True,
            headers={"User-Agent": UA, "Accept": "application/json"},
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=10),
        )

    async def _get_json(self, url: str, timeout: float = 14.0) -> Optional[Any]:
        try:
            async with self._client(timeout) as c:
                r = await c.get(url)
                if r.status_code >= 400:
                    return None
                if not r.content or r.content[:1] not in (b"{", b"["):
                    return None
                return r.json()
        except Exception:
            return None

    def _piped_order(self) -> List[str]:
        pool = list(PIPED_POOL)
        if self._prefer_piped and self._prefer_piped in pool:
            pool.remove(self._prefer_piped)
            pool.insert(0, self._prefer_piped)
        return pool

    def _inv_order(self) -> List[str]:
        pool = list(INVIDIOUS_POOL)
        if self._prefer_inv and self._prefer_inv in pool:
            pool.remove(self._prefer_inv)
            pool.insert(0, self._prefer_inv)
        return pool

    # ── public streams ────────────────────────────────────
    async def get_streams(self, video_id: str) -> dict:
        vid = extract_id(video_id)
        errors: List[str] = []

        # Round 1: parallel Piped (fast)
        data = await self._race_piped(vid)
        if data:
            return data
        errors.append("piped-round1")

        # Round 2: parallel Invidious
        data = await self._race_invidious(vid)
        if data:
            return data
        errors.append("invidious")

        # Round 3: Piped again with longer timeout (cold starts)
        data = await self._race_piped(vid, timeout=20.0)
        if data:
            return data
        errors.append("piped-round2")

        # Round 4: yt-dlp
        data = await self._streams_ytdlp(vid)
        if data:
            return data
        errors.append("yt-dlp")

        raise RuntimeError(
            "All stream backends failed after retries (" + ", ".join(errors) + "). Try again in a few seconds."
        )

    async def _race_piped(self, vid: str, timeout: float = 14.0) -> Optional[dict]:
        async def one(base: str) -> Optional[dict]:
            j = await self._get_json(f"{base}/streams/{vid}", timeout=timeout)
            if not isinstance(j, dict) or not j.get("title"):
                return None
            if not (j.get("videoStreams") or j.get("audioStreams")):
                return None
            self._prefer_piped = base
            return self._norm_piped(j, vid, base)

        bases = self._piped_order()
        tasks = [asyncio.create_task(one(b)) for b in bases]
        try:
            for fut in asyncio.as_completed(tasks):
                try:
                    res = await fut
                except Exception:
                    continue
                if res:
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                    return res
        except Exception:
            pass
        return None

    async def _race_invidious(self, vid: str) -> Optional[dict]:
        async def one(base: str) -> Optional[dict]:
            j = await self._get_json(f"{base}/api/v1/videos/{vid}", timeout=14.0)
            if not isinstance(j, dict) or not j.get("title"):
                return None
            formats = (j.get("formatStreams") or []) + (j.get("adaptiveFormats") or [])
            if not formats:
                return None
            self._prefer_inv = base
            return self._norm_invidious(j, vid, base)

        tasks = [asyncio.create_task(one(b)) for b in self._inv_order()]
        try:
            for fut in asyncio.as_completed(tasks):
                try:
                    res = await fut
                except Exception:
                    continue
                if res:
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                    return res
        except Exception:
            pass
        return None

    def _h(self, q) -> int:
        if not q:
            return 0
        m = re.search(r"(\d{3,4})", str(q))
        return int(m.group(1)) if m else 0

    def _norm_piped(self, j: dict, vid: str, instance: str) -> dict:
        video_streams, audio_streams, muxed = [], [], []
        for s in j.get("videoStreams") or []:
            url = s.get("url")
            if not url:
                continue
            item = {
                "url": url,
                "itag": s.get("itag"),
                "mimeType": s.get("mimeType") or s.get("format"),
                "quality": s.get("quality") or s.get("qualityLabel"),
                "height": self._h(s.get("quality") or s.get("qualityLabel")),
                "bitrate": s.get("bitrate"),
                "codec": s.get("codec"),
                "container": s.get("format"),
                "has_audio": not s.get("videoOnly", True),
                "has_video": True,
                "cdn": "piped",
            }
            (video_streams if s.get("videoOnly") else muxed).append(item)
        for s in j.get("audioStreams") or []:
            url = s.get("url")
            if not url:
                continue
            audio_streams.append({
                "url": url,
                "itag": s.get("itag"),
                "mimeType": s.get("mimeType") or s.get("format"),
                "quality": s.get("quality"),
                "bitrate": s.get("bitrate"),
                "codec": s.get("codec"),
                "container": s.get("format"),
                "has_audio": True,
                "has_video": False,
                "cdn": "piped",
            })
        video_streams.sort(key=lambda x: x.get("height") or 0, reverse=True)
        audio_streams.sort(key=lambda x: x.get("bitrate") or 0, reverse=True)
        muxed.sort(key=lambda x: x.get("height") or 0, reverse=True)
        best_a = audio_streams[0] if audio_streams else None
        qualities = []
        for m in muxed:
            qualities.append({
                "label": m.get("quality") or f"{m.get('height')}p",
                "height": m.get("height"),
                "kind": "muxed",
                "url": m["url"],
                "video_url": m["url"],
                "audio_url": None,
                "has_audio": True,
                "play_mode": "single",
            })
        for v in video_streams:
            if not best_a:
                break
            qualities.append({
                "label": v.get("quality") or f"{v.get('height')}p",
                "height": v.get("height"),
                "kind": "paired",
                "url": None,
                "video_url": v["url"],
                "audio_url": best_a["url"],
                "has_audio": True,
                "play_mode": "dual",
            })
        qualities.sort(key=lambda x: x.get("height") or 0, reverse=True)
        direct_video = (muxed[0]["url"] if muxed else None) or (
            video_streams[0]["url"] if video_streams else None
        )
        direct_audio = best_a["url"] if best_a else None
        # If no separate audio, some muxed still play as audio-capable
        if not direct_audio and direct_video:
            direct_audio = direct_video
        return {
            "videoId": vid,
            "title": j.get("title") or "",
            "description": (j.get("description") or "")[:2000],
            "thumbnail": j.get("thumbnailUrl") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            "duration": j.get("duration") or 0,
            "uploader": j.get("uploader") or "",
            "uploaderUrl": j.get("uploaderUrl") or "",
            "uploaderId": (j.get("uploaderUrl") or "").rstrip("/").split("/")[-1],
            "views": j.get("views") or 0,
            "likes": j.get("likes") or 0,
            "uploadDate": j.get("uploadDate") or j.get("uploadedDate") or "",
            "liveNow": bool(j.get("livestream")),
            "hls": j.get("hls"),
            "dash": j.get("dash"),
            "videoStreams": video_streams,
            "audioStreams": audio_streams,
            "muxedStreams": muxed,
            "qualities": qualities,
            "default_quality": qualities[0] if qualities else None,
            "direct_video": direct_video,
            "direct_audio": direct_audio,
            "direct_play": direct_video or direct_audio,
            "mp4": direct_video,
            "mp3_audio": direct_audio,
            "provider": "piped",
            "instance": instance,
            "webpage_url": f"https://www.youtube.com/watch?v={vid}",
        }

    def _norm_invidious(self, j: dict, vid: str, base: str) -> dict:
        video_streams, audio_streams, muxed = [], [], []
        for f in (j.get("formatStreams") or []):
            url = f.get("url")
            if not url:
                continue
            muxed.append({
                "url": url,
                "itag": f.get("itag"),
                "mimeType": f.get("type"),
                "quality": f.get("qualityLabel") or f.get("quality"),
                "height": self._h(f.get("qualityLabel") or f.get("quality")),
                "bitrate": f.get("bitrate"),
                "container": f.get("container"),
                "has_audio": True,
                "has_video": True,
                "cdn": "invidious",
            })
        for f in (j.get("adaptiveFormats") or []):
            url = f.get("url")
            if not url:
                continue
            t = f.get("type") or ""
            item = {
                "url": url,
                "itag": f.get("itag"),
                "mimeType": t,
                "quality": f.get("qualityLabel") or f.get("quality") or f.get("audioQuality"),
                "height": self._h(f.get("qualityLabel") or f.get("quality")),
                "bitrate": f.get("bitrate"),
                "container": f.get("container"),
                "has_audio": t.startswith("audio"),
                "has_video": t.startswith("video"),
                "cdn": "invidious",
            }
            if t.startswith("audio"):
                audio_streams.append(item)
            else:
                video_streams.append(item)
        fake = {
            "title": j.get("title"),
            "description": j.get("description"),
            "thumbnailUrl": (j.get("videoThumbnails") or [{}])[0].get("url"),
            "duration": j.get("lengthSeconds"),
            "uploader": j.get("author"),
            "uploaderUrl": j.get("authorUrl"),
            "views": j.get("viewCount"),
            "likes": j.get("likeCount"),
            "uploadDate": j.get("publishedText"),
            "livestream": j.get("liveNow"),
            "hls": j.get("hlsUrl"),
            "dash": j.get("dashUrl"),
            "videoStreams": [
                {**v, "videoOnly": True, "format": v.get("container"), "qualityLabel": v.get("quality")}
                for v in video_streams
            ]
            + [
                {**m, "videoOnly": False, "format": m.get("container"), "qualityLabel": m.get("quality")}
                for m in muxed
            ],
            "audioStreams": audio_streams,
        }
        out = self._norm_piped(fake, vid, base)
        out["provider"] = "invidious"
        return out

    async def _streams_ytdlp(self, vid: str) -> Optional[dict]:
        if not yt_dlp:
            return None
        opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 25,
            "retries": 2,
            "ignore_no_formats_error": True,
            "extractor_args": {"youtube": {"player_client": ["android", "ios", "web"]}},
        }
        p = self.cookies.path()
        if p:
            opts["cookiefile"] = str(p)

        def _do():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False) or {}

        try:
            info = await self._run(_do)
        except Exception:
            return None
        formats = info.get("formats") or []
        if not any(f.get("url") for f in formats):
            return None
        video_streams, audio_streams, muxed = [], [], []
        for f in formats:
            url = f.get("url")
            if not url:
                continue
            vc, ac = f.get("vcodec") or "none", f.get("acodec") or "none"
            item = {
                "url": url,
                "itag": f.get("format_id"),
                "mimeType": f.get("mime_type") or f.get("ext"),
                "quality": f.get("format_note") or (f"{f.get('height')}p" if f.get("height") else None),
                "height": f.get("height"),
                "bitrate": int((f.get("tbr") or 0) * 1000) if f.get("tbr") else None,
                "codec": vc if vc != "none" else ac,
                "container": f.get("ext"),
                "has_audio": ac != "none",
                "has_video": vc != "none",
                "cdn": "googlevideo" if "googlevideo.com" in url else "other",
            }
            if vc != "none" and ac != "none":
                muxed.append(item)
            elif vc != "none":
                video_streams.append(item)
            elif ac != "none":
                audio_streams.append(item)
        if not video_streams and not audio_streams and not muxed:
            return None
        fake = {
            "title": info.get("title"),
            "description": info.get("description"),
            "thumbnailUrl": (info.get("thumbnails") or [{}])[-1].get("url"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader") or info.get("channel"),
            "uploaderUrl": info.get("uploader_url") or info.get("channel_url"),
            "views": info.get("view_count"),
            "likes": info.get("like_count"),
            "uploadDate": info.get("upload_date"),
            "livestream": info.get("is_live"),
            "hls": info.get("hls_url") or info.get("manifest_url"),
            "videoStreams": [
                {**v, "videoOnly": True, "format": v.get("container"), "qualityLabel": v.get("quality")}
                for v in video_streams
            ]
            + [
                {**m, "videoOnly": False, "format": m.get("container"), "qualityLabel": m.get("quality")}
                for m in muxed
            ],
            "audioStreams": audio_streams,
        }
        out = self._norm_piped(fake, vid, "yt-dlp")
        out["provider"] = "yt-dlp"
        return out

    # ── catalog endpoints ─────────────────────────────────
    async def search(self, q: str, filter: str = "all", limit: int = 20) -> dict:
        for base in self._piped_order():
            try:
                async with self._client(16) as c:
                    r = await c.get(f"{base}/search", params={"q": q, "filter": "all"})
                    if r.status_code >= 400:
                        continue
                    j = r.json()
            except Exception:
                continue
            items = []
            rows = j.get("items") if isinstance(j, dict) else j
            for e in rows or []:
                if not isinstance(e, dict):
                    continue
                vid = e.get("url", "").split("v=")[-1] if "v=" in (e.get("url") or "") else (e.get("id") or "")
                vid = str(vid).replace("/watch?v=", "")
                items.append({
                    "type": e.get("type") or "video",
                    "videoId": vid,
                    "title": e.get("title") or "",
                    "uploader": e.get("uploaderName") or e.get("uploader") or "",
                    "duration": e.get("duration") or 0,
                    "views": e.get("views") or e.get("viewCount") or 0,
                    "thumbnail": e.get("thumbnail") or (f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else ""),
                    "url": f"https://www.youtube.com/watch?v={vid}" if vid else "",
                })
                if len(items) >= limit:
                    break
            if items:
                self._prefer_piped = base
                return {"query": q, "filter": filter, "count": len(items), "items": items, "provider": "piped"}
        return {"query": q, "filter": filter, "count": 0, "items": [], "provider": "none"}

    async def trending(self, region: str = "US", category: str = "default") -> dict:
        for base in self._piped_order():
            try:
                async with self._client(16) as c:
                    r = await c.get(f"{base}/trending", params={"region": region})
                    if r.status_code >= 400:
                        continue
                    j = r.json()
            except Exception:
                continue
            items = []
            for e in (j if isinstance(j, list) else [])[:30]:
                vid = (e.get("url") or "").split("v=")[-1] if e.get("url") else e.get("id")
                items.append({
                    "videoId": vid,
                    "title": e.get("title") or "",
                    "uploader": e.get("uploaderName") or "",
                    "duration": e.get("duration") or 0,
                    "views": e.get("views") or 0,
                    "thumbnail": e.get("thumbnail") or "",
                    "url": f"https://www.youtube.com/watch?v={vid}" if vid else "",
                })
            if items:
                self._prefer_piped = base
                return {"region": region, "category": category, "items": items, "provider": "piped"}
        return {"region": region, "category": category, "items": [], "provider": "none"}

    async def get_channel(self, channel_id: str, limit: int = 20) -> dict:
        cid = channel_id.strip()
        for base in self._piped_order():
            try:
                async with self._client(16) as c:
                    r = await c.get(f"{base}/channel/{cid}")
                    if r.status_code >= 400:
                        continue
                    j = r.json()
            except Exception:
                continue
            if not isinstance(j, dict):
                continue
            videos = []
            for e in (j.get("relatedStreams") or [])[:limit]:
                vid = (e.get("url") or "").split("v=")[-1]
                videos.append({
                    "videoId": vid,
                    "title": e.get("title") or "",
                    "duration": e.get("duration") or 0,
                    "views": e.get("views") or 0,
                    "thumbnail": e.get("thumbnail") or "",
                    "url": f"https://www.youtube.com/watch?v={vid}" if vid else "",
                })
            if j.get("name") or videos:
                self._prefer_piped = base
                return {
                    "id": j.get("id") or cid,
                    "name": j.get("name") or "",
                    "description": (j.get("description") or "")[:1000],
                    "subscriberCount": j.get("subscriberCount") or 0,
                    "thumbnail": j.get("avatarUrl") or "",
                    "url": j.get("url") or "",
                    "videos": videos,
                    "count": len(videos),
                    "provider": "piped",
                }
        return {"id": cid, "name": "", "videos": [], "count": 0, "provider": "none"}

    async def get_playlist(self, playlist_id: str, limit: int = 50) -> dict:
        pid = playlist_id.strip()
        for base in self._piped_order():
            try:
                async with self._client(16) as c:
                    r = await c.get(f"{base}/playlists/{pid}")
                    if r.status_code >= 400:
                        continue
                    j = r.json()
            except Exception:
                continue
            if not isinstance(j, dict):
                continue
            videos = []
            for e in (j.get("relatedStreams") or [])[:limit]:
                vid = (e.get("url") or "").split("v=")[-1]
                videos.append({
                    "videoId": vid,
                    "title": e.get("title") or "",
                    "uploader": e.get("uploaderName") or "",
                    "duration": e.get("duration") or 0,
                    "thumbnail": e.get("thumbnail") or "",
                    "url": f"https://www.youtube.com/watch?v={vid}" if vid else "",
                })
            if j.get("name") or videos:
                self._prefer_piped = base
                return {
                    "id": j.get("id") or pid,
                    "title": j.get("name") or "",
                    "description": (j.get("description") or "")[:1000],
                    "uploader": j.get("uploader") or "",
                    "videoCount": j.get("videos") or len(videos),
                    "thumbnail": j.get("thumbnailUrl") or "",
                    "videos": videos,
                    "count": len(videos),
                    "provider": "piped",
                }
        return {"id": pid, "title": "", "videos": [], "count": 0, "provider": "none"}

    async def get_comments(self, video_id: str, limit: int = 30) -> dict:
        vid = extract_id(video_id)
        for base in self._piped_order():
            j = await self._get_json(f"{base}/comments/{vid}")
            if not isinstance(j, dict):
                continue
            comments = []
            for c in (j.get("comments") or [])[:limit]:
                comments.append({
                    "author": c.get("author") or "",
                    "authorId": c.get("commentorUrl") or "",
                    "text": c.get("commentText") or c.get("text") or "",
                    "likeCount": c.get("likeCount") or 0,
                    "time": c.get("commentedTime") or "",
                    "id": c.get("commentId") or "",
                })
            if comments:
                return {"videoId": vid, "comments": comments, "count": len(comments), "provider": "piped"}
        return {"videoId": vid, "comments": [], "count": 0, "provider": "none"}

    async def suggestions(self, q: str) -> dict:
        for base in self._piped_order():
            try:
                async with self._client(10) as c:
                    r = await c.get(f"{base}/opensearch/suggestions", params={"query": q})
                    if r.status_code >= 400:
                        continue
                    j = r.json()
                    if isinstance(j, list) and len(j) >= 2 and isinstance(j[1], list):
                        return {"query": q, "suggestions": j[1][:10], "provider": "piped"}
            except Exception:
                continue
        return {"query": q, "suggestions": [], "provider": "none"}

    async def extract_info(self, url: str) -> dict:
        return await self.get_streams(extract_id(url))

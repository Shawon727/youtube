"""YouTube section — LibreTube/Piped style via yt-dlp. Always returns non-empty structure."""
from __future__ import annotations
import asyncio, re
from typing import Any, Dict, List, Optional
from cookie_manager import CookieManager

try:
    import yt_dlp
except ImportError:
    yt_dlp = None  # type: ignore


def extract_id(raw: str) -> str:
    s = (raw or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{6,20}", s):
        return s
    m = re.search(r"(?:v=|/shorts/|youtu\.be/|embed/|live/)([A-Za-z0-9_-]{6,20})", s)
    return m.group(1) if m else s


class YouTubeAPI:
    def __init__(self) -> None:
        self.cookies = CookieManager()
        self._base = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "socket_timeout": 25,
            "retries": 3,
            "extractor_args": {"youtube": {"player_client": ["android", "ios", "web"]}},
        }

    def _opts(self, extra: Optional[dict] = None) -> dict:
        o = dict(self._base)
        p = self.cookies.path()
        if p:
            o["cookiefile"] = str(p)
        if extra:
            o.update(extra)
        return o

    def reload_cookies(self) -> None:
        pass

    async def _run(self, fn, *a, **kw):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: fn(*a, **kw))

    def _extract(self, url: str, opts: Optional[dict] = None) -> dict:
        if not yt_dlp:
            raise RuntimeError("yt-dlp not installed")
        with yt_dlp.YoutubeDL(self._opts(opts)) as ydl:
            return ydl.extract_info(url, download=False) or {}

    # ── streams (direct CDN) ──────────────────────────────
    async def get_streams(self, video_id: str) -> dict:
        vid = extract_id(video_id)
        info = await self._run(self._extract, f"https://www.youtube.com/watch?v={vid}")
        return self._norm_streams(info, vid)

    def _norm_streams(self, info: dict, vid: str) -> dict:
        formats = info.get("formats") or []
        video_streams, audio_streams, muxed = [], [], []

        for f in formats:
            url = f.get("url")
            if not url:
                continue
            vc = f.get("vcodec") or "none"
            ac = f.get("acodec") or "none"
            h = f.get("height")
            tbr = f.get("tbr") or f.get("abr") or 0
            item = {
                "url": url,  # direct googlevideo CDN
                "itag": f.get("format_id"),
                "mimeType": f.get("mime_type") or f.get("ext"),
                "bitrate": int(tbr * 1000) if tbr else None,
                "quality": f.get("format_note") or (f"{h}p" if h else None),
                "height": h,
                "width": f.get("width"),
                "fps": f.get("fps"),
                "codec": vc if vc != "none" else ac,
                "container": f.get("ext"),
                "filesize": f.get("filesize") or f.get("filesize_approx"),
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

        video_streams.sort(key=lambda x: x.get("height") or 0, reverse=True)
        audio_streams.sort(key=lambda x: x.get("bitrate") or 0, reverse=True)
        muxed.sort(key=lambda x: x.get("height") or 0, reverse=True)

        best_audio = audio_streams[0] if audio_streams else None
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
                "cdn": m.get("cdn"),
            })
        seen_h = {q.get("height") for q in qualities}
        for v in video_streams:
            h = v.get("height")
            if h in seen_h or not best_audio:
                continue
            qualities.append({
                "label": v.get("quality") or f"{h}p",
                "height": h,
                "kind": "paired",
                "url": None,
                "video_url": v["url"],
                "audio_url": best_audio["url"],
                "has_audio": True,
                "play_mode": "dual",
                "cdn": v.get("cdn"),
            })
            seen_h.add(h)
        qualities.sort(key=lambda x: x.get("height") or 0, reverse=True)

        thumbs = info.get("thumbnails") or []
        thumb = thumbs[-1]["url"] if thumbs else (f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else None)

        best_video_url = (muxed[0]["url"] if muxed else None) or (video_streams[0]["url"] if video_streams else None)
        best_audio_url = best_audio["url"] if best_audio else None

        return {
            "videoId": vid or info.get("id"),
            "title": info.get("title") or "",
            "description": (info.get("description") or "")[:2000],
            "thumbnail": thumb,
            "duration": info.get("duration") or 0,
            "uploader": info.get("uploader") or info.get("channel") or "",
            "uploaderUrl": info.get("uploader_url") or info.get("channel_url") or "",
            "uploaderId": info.get("channel_id") or info.get("uploader_id") or "",
            "views": info.get("view_count") or 0,
            "likes": info.get("like_count") or 0,
            "uploadDate": info.get("upload_date") or "",
            "liveNow": bool(info.get("is_live")),
            "isUpcoming": bool(info.get("is_upcoming")),
            "hls": info.get("hls_url") or info.get("manifest_url"),
            "videoStreams": video_streams,
            "audioStreams": audio_streams,
            "muxedStreams": muxed,
            "qualities": qualities,
            "default_quality": qualities[0] if qualities else None,
            # convenience direct CDN links
            "direct_video": best_video_url,
            "direct_audio": best_audio_url,
            "direct_play": best_video_url or best_audio_url,
            "provider": "yt-dlp",
            "webpage_url": info.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}",
        }

    # ── search ────────────────────────────────────────────
    async def search(self, q: str, filter: str = "all", limit: int = 20) -> dict:
        if not yt_dlp:
            raise RuntimeError("yt-dlp not installed")
        opts = self._opts({"extract_flat": "in_playlist", "playlistend": limit})
        query = f"ytsearch{limit}:{q}"

        def _do():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(query, download=False) or {}

        info = await self._run(_do)
        items = []
        for e in (info.get("entries") or []):
            if not e:
                continue
            vid = e.get("id")
            items.append({
                "type": e.get("_type") or "video",
                "videoId": vid,
                "title": e.get("title") or "",
                "uploader": e.get("uploader") or e.get("channel") or "",
                "uploaderId": e.get("channel_id") or "",
                "duration": e.get("duration") or 0,
                "views": e.get("view_count") or 0,
                "thumbnail": ((e.get("thumbnails") or [{}])[-1].get("url")
                              or (f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else "")),
                "url": e.get("url") or e.get("webpage_url")
                       or (f"https://www.youtube.com/watch?v={vid}" if vid else ""),
                "liveNow": e.get("live_status") == "is_live",
            })
        return {"query": q, "filter": filter, "count": len(items), "items": items[:limit]}

    # ── trending ──────────────────────────────────────────
    async def trending(self, region: str = "US", category: str = "default") -> dict:
        url = f"https://www.youtube.com/feed/trending?gl={region}"
        opts = self._opts({"extract_flat": "in_playlist", "playlistend": 30})

        def _do():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False) or {}

        try:
            info = await self._run(_do)
        except Exception:
            # soft fallback → search
            s = await self.search("trending", limit=20)
            return {"region": region, "category": category, "items": s.get("items") or [], "fallback": True}

        items = []
        for e in (info.get("entries") or []):
            if not e:
                continue
            vid = e.get("id")
            items.append({
                "videoId": vid,
                "title": e.get("title") or "",
                "uploader": e.get("uploader") or e.get("channel") or "",
                "uploaderUrl": e.get("uploader_url") or e.get("channel_url") or "",
                "duration": e.get("duration") or 0,
                "views": e.get("view_count") or 0,
                "thumbnail": ((e.get("thumbnails") or [{}])[-1].get("url")
                              or (f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else "")),
                "uploadedDate": e.get("upload_date") or "",
                "url": f"https://www.youtube.com/watch?v={vid}" if vid else "",
            })
        if not items:
            s = await self.search("trending", limit=20)
            return {"region": region, "category": category, "items": s.get("items") or [], "fallback": True}
        return {"region": region, "category": category, "items": items}

    # ── channel ───────────────────────────────────────────
    async def get_channel(self, channel_id: str, limit: int = 20) -> dict:
        cid = channel_id.strip()
        if cid.startswith("@"):
            url = f"https://www.youtube.com/{cid}/videos"
        elif cid.startswith("UC"):
            url = f"https://www.youtube.com/channel/{cid}/videos"
        else:
            url = f"https://www.youtube.com/channel/{cid}/videos"
        opts = self._opts({"extract_flat": "in_playlist", "playlistend": limit})

        def _do():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False) or {}

        info = await self._run(_do)
        videos = []
        for e in (info.get("entries") or [])[:limit]:
            if not e:
                continue
            vid = e.get("id")
            videos.append({
                "videoId": vid,
                "title": e.get("title") or "",
                "duration": e.get("duration") or 0,
                "views": e.get("view_count") or 0,
                "thumbnail": ((e.get("thumbnails") or [{}])[-1].get("url")
                              or (f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else "")),
                "url": f"https://www.youtube.com/watch?v={vid}" if vid else "",
            })
        return {
            "id": info.get("channel_id") or info.get("id") or cid,
            "name": info.get("channel") or info.get("uploader") or info.get("title") or "",
            "description": (info.get("description") or "")[:1000],
            "subscriberCount": info.get("channel_follower_count") or 0,
            "thumbnail": ((info.get("thumbnails") or [{}])[-1].get("url") or ""),
            "url": info.get("channel_url") or info.get("uploader_url") or "",
            "videos": videos,
            "count": len(videos),
        }

    # ── playlist ──────────────────────────────────────────
    async def get_playlist(self, playlist_id: str, limit: int = 50) -> dict:
        pid = playlist_id.strip()
        url = f"https://www.youtube.com/playlist?list={pid}"
        opts = self._opts({"extract_flat": "in_playlist", "playlistend": limit})

        def _do():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False) or {}

        info = await self._run(_do)
        videos = []
        for e in (info.get("entries") or [])[:limit]:
            if not e:
                continue
            vid = e.get("id")
            videos.append({
                "videoId": vid,
                "title": e.get("title") or "",
                "uploader": e.get("uploader") or e.get("channel") or "",
                "duration": e.get("duration") or 0,
                "thumbnail": ((e.get("thumbnails") or [{}])[-1].get("url")
                              or (f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else "")),
                "url": f"https://www.youtube.com/watch?v={vid}" if vid else "",
            })
        return {
            "id": info.get("id") or pid,
            "title": info.get("title") or "",
            "description": (info.get("description") or "")[:1000],
            "uploader": info.get("uploader") or info.get("channel") or "",
            "videoCount": info.get("playlist_count") or len(videos),
            "thumbnail": ((info.get("thumbnails") or [{}])[-1].get("url") or ""),
            "videos": videos,
            "count": len(videos),
        }

    # ── comments ──────────────────────────────────────────
    async def get_comments(self, video_id: str, limit: int = 30) -> dict:
        vid = extract_id(video_id)
        opts = self._opts({"getcomments": True})

        def _do():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False) or {}

        try:
            info = await self._run(_do)
        except Exception as e:
            return {"videoId": vid, "comments": [], "count": 0, "note": str(e)[:120]}

        comments = []
        for c in (info.get("comments") or [])[:limit]:
            comments.append({
                "author": c.get("author") or "",
                "authorId": c.get("author_id") or "",
                "text": c.get("text") or "",
                "likeCount": c.get("like_count") or 0,
                "time": c.get("timestamp") or c.get("time_text") or "",
                "id": c.get("id") or "",
            })
        return {"videoId": vid, "comments": comments, "count": len(comments)}

    async def suggestions(self, q: str) -> dict:
        res = await self.search(q, limit=8)
        titles = [i.get("title") for i in res.get("items") or [] if i.get("title")]
        return {"query": q, "suggestions": titles}

    async def extract_info(self, url: str) -> dict:
        info = await self._run(self._extract, url)
        for k in ("formats", "thumbnails", "automatic_captions", "subtitles", "heatmap", "comments"):
            info.pop(k, None)
        return info

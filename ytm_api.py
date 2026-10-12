"""YouTube Music — SimpMusic style (ytmusicapi) + yt-dlp for direct audio CDN."""
from __future__ import annotations
import asyncio, re
from typing import Any, Dict, List, Optional
from cookie_manager import CookieManager

try:
    from ytmusicapi import YTMusic
except ImportError:
    YTMusic = None  # type: ignore

try:
    import yt_dlp
except ImportError:
    yt_dlp = None  # type: ignore


def extract_id(raw: str) -> str:
    s = (raw or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{6,20}", s):
        return s
    m = re.search(r"(?:v=|/shorts/|youtu\.be/|embed/)([A-Za-z0-9_-]{6,20})", s)
    return m.group(1) if m else s


class YouTubeMusicAPI:
    def __init__(self) -> None:
        self.cookies = CookieManager()
        self._ytm: Any = None
        self._init()

    def _init(self) -> None:
        if not YTMusic:
            self._ytm = None
            return
        path = self.cookies.path()
        try:
            self._ytm = YTMusic(str(path)) if path else YTMusic()
        except Exception:
            try:
                self._ytm = YTMusic()
            except Exception:
                self._ytm = None

    def reload_cookies(self) -> None:
        self._init()

    def _c(self):
        if not self._ytm:
            raise RuntimeError("ytmusicapi not available")
        return self._ytm

    async def _run(self, fn, *a, **kw):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: fn(*a, **kw))

    async def search(self, q: str, filter: str = "songs", limit: int = 20) -> dict:
        fmap = {
            "songs": "songs", "videos": "videos", "albums": "albums",
            "artists": "artists", "playlists": "playlists",
            "community_playlists": "community_playlists",
            "featured_playlists": "featured_playlists", "podcasts": "podcasts",
        }
        f = fmap.get(filter, "songs")
        client = self._c()

        def _do():
            return client.search(q, filter=f, limit=limit) or []

        results = await self._run(_do)
        return {"query": q, "filter": f, "count": len(results), "items": results[:limit]}

    async def suggestions(self, q: str) -> dict:
        client = self._c()

        def _do():
            return client.get_search_suggestions(q) or []

        s = await self._run(_do)
        return {"query": q, "suggestions": s}

    async def home(self, limit: int = 6) -> dict:
        client = self._c()

        def _do():
            return client.get_home(limit=limit) or []

        data = await self._run(_do)
        return {"sections": data, "count": len(data) if isinstance(data, list) else 0}

    async def charts(self, country: str = "ZZ") -> dict:
        client = self._c()

        def _do():
            return client.get_charts(country=country) or {}

        data = await self._run(_do)
        return data if isinstance(data, dict) else {"data": data}

    async def get_moods_and_genres(self) -> dict:
        client = self._c()

        def _do():
            return client.get_mood_categories() or {}

        return await self._run(_do)

    async def get_artist(self, artist_id: str) -> dict:
        client = self._c()

        def _do():
            return client.get_artist(artist_id) or {}

        return await self._run(_do)

    async def get_album(self, browse_id: str) -> dict:
        client = self._c()

        def _do():
            return client.get_album(browse_id) or {}

        return await self._run(_do)

    async def get_playlist(self, playlist_id: str, limit: int = 100) -> dict:
        client = self._c()
        pid = playlist_id[2:] if playlist_id.startswith("VL") else playlist_id

        def _do():
            return client.get_playlist(pid, limit=limit) or {}

        return await self._run(_do)

    async def get_watch_playlist(
        self, video_id: str, playlist_id: Optional[str] = None, radio: bool = True
    ) -> dict:
        client = self._c()
        vid = extract_id(video_id)

        def _do():
            return client.get_watch_playlist(videoId=vid, playlistId=playlist_id, limit=50) or {}

        return await self._run(_do)

    async def get_lyrics(self, video_id: str) -> dict:
        client = self._c()
        vid = extract_id(video_id)

        def _do():
            wp = client.get_watch_playlist(videoId=vid) or {}
            lid = wp.get("lyrics")
            if not lid:
                return {"lyrics": None, "source": None}
            return client.get_lyrics(lid) or {"lyrics": None}

        try:
            data = await self._run(_do)
            return data if isinstance(data, dict) else {"lyrics": data}
        except Exception as e:
            return {"lyrics": None, "error": str(e)[:150]}

    # ── direct audio CDN via yt-dlp ───────────────────────
    async def play(self, video_id: str) -> dict:
        if not yt_dlp:
            raise RuntimeError("yt-dlp not installed")
        vid = extract_id(video_id)
        cookie_path = self.cookies.path()
        opts: Dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "format": "bestaudio/best",
            "socket_timeout": 25,
            "retries": 3,
            "extractor_args": {
                "youtube": {"player_client": ["android_music", "android", "ios", "web"]}
            },
        }
        if cookie_path:
            opts["cookiefile"] = str(cookie_path)

        def _do():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(
                    f"https://music.youtube.com/watch?v={vid}", download=False
                ) or {}

        info = await self._run(_do)
        formats = info.get("formats") or []
        audio_formats = [
            f for f in formats
            if (f.get("acodec") or "none") != "none"
            and (f.get("vcodec") or "none") == "none"
            and f.get("url")
        ]
        audio_formats.sort(key=lambda x: (x.get("abr") or x.get("tbr") or 0), reverse=True)

        best = audio_formats[0] if audio_formats else None
        alts = []
        for f in audio_formats[:6]:
            alts.append({
                "url": f.get("url"),
                "abr": f.get("abr") or f.get("tbr"),
                "ext": f.get("ext"),
                "codec": f.get("acodec"),
                "format_id": f.get("format_id"),
                "filesize": f.get("filesize") or f.get("filesize_approx"),
                "cdn": "googlevideo" if "googlevideo.com" in (f.get("url") or "") else "other",
            })

        thumbs = info.get("thumbnails") or []
        thumb = thumbs[-1]["url"] if thumbs else None
        audio_url = best.get("url") if best else None

        return {
            "videoId": vid,
            "title": info.get("title") or "",
            "artist": info.get("artist") or info.get("uploader") or info.get("channel") or "",
            "album": info.get("album") or "",
            "duration": info.get("duration") or 0,
            "thumbnail": thumb or "",
            # main direct CDN links
            "audio_url": audio_url,
            "directUrl": audio_url,
            "direct_audio": audio_url,
            "abr": (best.get("abr") or best.get("tbr")) if best else None,
            "ext": best.get("ext") if best else None,
            "codec": best.get("acodec") if best else None,
            "formats": alts,
            "expires_note": "googlevideo URL expires ~6 hours — call /ytm/play again when needed",
            "provider": "yt-dlp",
            "webpage_url": info.get("webpage_url") or f"https://music.youtube.com/watch?v={vid}",
        }

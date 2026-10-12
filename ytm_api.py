"""YouTube Music — ytmusicapi meta + Piped/yt-dlp streams."""
from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, Optional

import httpx

from cookie_manager import CookieManager
from youtube_api import YouTubeAPI, PIPED, UA

try:
    from ytmusicapi import YTMusic
except ImportError:
    YTMusic = None  # type: ignore


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
        self._ytm_ready = False
        self._yt = YouTubeAPI()

    def _init(self) -> None:
        if self._ytm_ready and self._ytm is not None:
            return
        self._ytm = None
        if not YTMusic:
            self._ytm_ready = True
            return
        path = self.cookies.path()
        try:
            self._ytm = YTMusic(str(path)) if path else YTMusic()
        except Exception:
            try:
                self._ytm = YTMusic()
            except Exception:
                self._ytm = None
        self._ytm_ready = True

    def reload_cookies(self) -> None:
        self._ytm = None
        self._ytm_ready = False
        self._init()

    def _c(self):
        self._init()
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

        return {"query": q, "suggestions": await self._run(_do)}

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

    async def get_watch_playlist(self, video_id: str, playlist_id: Optional[str] = None, radio: bool = True) -> dict:
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

    async def play(self, video_id: str) -> dict:
        """Best audio CDN URL via Piped streams (Vercel-safe)."""
        vid = extract_id(video_id)
        streams = await self._yt.get_streams(vid)
        audio = streams.get("audioStreams") or []
        # also accept muxed as audio source
        direct_audio = streams.get("direct_audio")
        if not direct_audio and audio:
            direct_audio = audio[0].get("url")
        if not direct_audio:
            # last try: any stream url
            direct_audio = streams.get("direct_play")
        alts = []
        for a in audio[:6]:
            alts.append({
                "url": a.get("url"),
                "bitrate": a.get("bitrate"),
                "mimeType": a.get("mimeType"),
                "codec": a.get("codec"),
                "container": a.get("container"),
            })
        return {
            "videoId": vid,
            "title": streams.get("title") or "",
            "artist": streams.get("uploader") or "",
            "duration": streams.get("duration") or 0,
            "thumbnail": streams.get("thumbnail") or "",
            "audio_url": direct_audio,
            "directUrl": direct_audio,
            "direct_audio": direct_audio,
            "mp3_audio": direct_audio,
            "formats": alts,
            "expires_note": "Stream URLs expire — call again when needed",
            "provider": streams.get("provider"),
            "webpage_url": f"https://music.youtube.com/watch?v={vid}",
        }

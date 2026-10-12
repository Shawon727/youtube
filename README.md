# YT Stream API v1.1

YouTube + YouTube Music REST API  
**yt-dlp** + **ytmusicapi** · Direct **googlevideo CDN** links  
LibreTube / Piped style · SimpMusic style

---

## Quick start

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

| URL | |
|-----|--|
| http://127.0.0.1:8000/ | Home UI |
| http://127.0.0.1:8000/docs | Swagger |
| http://127.0.0.1:8000/cookies | Cookie Manager + Bookmarklet |
| http://127.0.0.1:8000/health | Health |

---

## Direct CDN streaming

### YouTube video
```
GET /yt/streams/{videoId}
```
Response keys:
- `direct_video` / `direct_play` — best muxed or video CDN URL
- `direct_audio` — best audio-only CDN URL
- `qualities[]` — all heights with `url` / `video_url` + `audio_url`
- `videoStreams` / `audioStreams` / `muxedStreams`

### YouTube Music audio
```
GET /ytm/play/{videoId}
```
Response keys:
- `audio_url` / `directUrl` / `direct_audio` — best audio googlevideo URL
- `formats[]` — alternate bitrates

> URLs expire ~6 hours. Call the endpoint again when needed.

---

## Cookie (from UI)

1. Open **/cookies**
2. Drag **🍪 Get YT Cookies** bookmarklet to bookmarks bar  
   → login on youtube.com → click bookmarklet → cookies auto-copied
3. Paste in **Paste Cookie string** tab, or upload `cookies.txt`

---

## All endpoints

### YouTube `/yt` · `/youtube`
- `GET /yt/streams/{id}`
- `GET /yt/search?q=&filter=&limit=`
- `GET /yt/trending?region=US&category=`
- `GET /yt/channel/{id}`
- `GET /yt/playlist/{id}`
- `GET /yt/comments/{id}`
- `GET /yt/suggestions?q=`
- `GET /yt/info?url=`

### YouTube Music `/ytm` · `/yt-music` · `/music`
- `GET /ytm/search?q=&filter=songs`
- `GET /ytm/home`
- `GET /ytm/charts?country=ZZ`
- `GET /ytm/artist/{id}`
- `GET /ytm/album/{id}`
- `GET /ytm/playlist/{id}`
- `GET /ytm/play/{id}` ← **direct audio CDN**
- `GET /ytm/next?video_id=`
- `GET /ytm/lyrics/{id}`
- `GET /ytm/suggestions?q=`
- `GET /ytm/moods`

### Cookies
- `GET /cookies` UI
- `GET /cookies/status`
- `POST /cookies/upload`
- `POST /cookies/paste`
- `DELETE /cookies`

---

## Deploy

**Vercel:** connect repo (vercel.json ready)  
**Railway / Render:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

Env (optional):
```
YTDLP_COOKIES=/path/to/cookies.txt
COOKIE_DIR=/data/cookies
```

---

## Files

```
main.py
api.py
youtube_api.py
ytm_api.py
cookie_manager.py
requirements.txt
vercel.json
Procfile
README.md
```

Not affiliated with Google / YouTube / LibreTube / SimpMusic.

"""
YT Stream API v1.1
YouTube + YouTube Music — yt-dlp + ytmusicapi
Direct googlevideo CDN links
"""
from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from youtube_api import YouTubeAPI
from ytm_api import YouTubeMusicAPI
from cookie_manager import CookieManager

CREATOR = "yt-stream"
VERSION = "1.1.0"

app = FastAPI(
    title="YT Stream API",
    description="YouTube + YouTube Music API (yt-dlp + ytmusicapi) — direct CDN streams",
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

yt = YouTubeAPI()
ytm = YouTubeMusicAPI()
cookies = CookieManager()


def ok(data: Any = None, **extra) -> dict:
    o = {"creator": CREATOR, "ok": True, "version": VERSION}
    if data is not None:
        o["data"] = data
    o.update(extra)
    return o


def fail(msg: str, **extra) -> dict:
    o = {"creator": CREATOR, "ok": False, "error": msg, "version": VERSION}
    o.update(extra)
    return o


# ── Home + Health ─────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home():
    return HOME_HTML


@app.get("/health")
async def health():
    return ok({"status": "alive", "ts": int(time.time()), "cookies": cookies.status()})


# ══════════════════════════════════════════════════════════
#  YOUTUBE
# ══════════════════════════════════════════════════════════
@app.get("/yt/streams/{video_id}")
@app.get("/youtube/streams/{video_id}")
async def yt_streams(video_id: str):
    """Direct googlevideo CDN video + audio streams (LibreTube style)."""
    try:
        data = await yt.get_streams(video_id)
        if not data.get("direct_play") and not data.get("videoStreams") and not data.get("audioStreams"):
            raise HTTPException(502, detail=fail("No streams found", videoId=video_id))
        return ok(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/search")
@app.get("/youtube/search")
async def yt_search(
    q: str = Query(..., min_length=1),
    filter: str = Query("all"),
    limit: int = Query(20, ge=1, le=50),
):
    try:
        data = await yt.search(q, filter=filter, limit=limit)
        return ok(data)
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/trending")
@app.get("/youtube/trending")
async def yt_trending(
    region: str = Query("US", min_length=2, max_length=2),
    category: str = Query("default"),
):
    try:
        data = await yt.trending(region=region.upper(), category=category)
        return ok(data)
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/channel/{channel_id}")
@app.get("/youtube/channel/{channel_id}")
async def yt_channel(channel_id: str, limit: int = Query(20, ge=1, le=50)):
    try:
        data = await yt.get_channel(channel_id, limit=limit)
        return ok(data)
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/playlist/{playlist_id}")
@app.get("/youtube/playlist/{playlist_id}")
async def yt_playlist(playlist_id: str, limit: int = Query(50, ge=1, le=100)):
    try:
        data = await yt.get_playlist(playlist_id, limit=limit)
        return ok(data)
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/comments/{video_id}")
@app.get("/youtube/comments/{video_id}")
async def yt_comments(video_id: str, limit: int = Query(30, ge=1, le=100)):
    try:
        data = await yt.get_comments(video_id, limit=limit)
        return ok(data)
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/suggestions")
@app.get("/youtube/suggestions")
async def yt_suggestions(q: str = Query(..., min_length=1)):
    try:
        return ok(await yt.suggestions(q))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/info")
@app.get("/youtube/info")
async def yt_info(url: str = Query(...)):
    try:
        return ok(await yt.extract_info(url))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


# ══════════════════════════════════════════════════════════
#  YOUTUBE MUSIC
# ══════════════════════════════════════════════════════════
@app.get("/ytm/search")
@app.get("/yt-music/search")
@app.get("/music/search")
async def ytm_search(
    q: str = Query(..., min_length=1),
    filter: str = Query("songs"),
    limit: int = Query(20, ge=1, le=50),
):
    try:
        return ok(await ytm.search(q, filter=filter, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/home")
@app.get("/yt-music/home")
async def ytm_home(limit: int = Query(6, ge=1, le=12)):
    try:
        return ok(await ytm.home(limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/charts")
@app.get("/yt-music/charts")
async def ytm_charts(country: str = Query("ZZ")):
    try:
        return ok(await ytm.charts(country=country.upper()))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/artist/{artist_id}")
@app.get("/yt-music/artist/{artist_id}")
async def ytm_artist(artist_id: str):
    try:
        return ok(await ytm.get_artist(artist_id))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/album/{browse_id}")
@app.get("/yt-music/album/{browse_id}")
async def ytm_album(browse_id: str):
    try:
        return ok(await ytm.get_album(browse_id))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/playlist/{playlist_id}")
@app.get("/yt-music/playlist/{playlist_id}")
async def ytm_playlist(playlist_id: str, limit: int = Query(100, ge=1, le=200)):
    try:
        return ok(await ytm.get_playlist(playlist_id, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/play/{video_id}")
@app.get("/yt-music/play/{video_id}")
@app.get("/music/play/{video_id}")
async def ytm_play(video_id: str):
    """Direct googlevideo audio CDN URL for YouTube Music track."""
    try:
        data = await ytm.play(video_id)
        if not data.get("audio_url") and not data.get("directUrl"):
            raise HTTPException(502, detail=fail("No audio stream found", videoId=video_id))
        return ok(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/next")
@app.get("/yt-music/next")
async def ytm_next(
    video_id: str = Query(...),
    playlist_id: Optional[str] = Query(None),
    radio: bool = Query(True),
):
    try:
        return ok(await ytm.get_watch_playlist(video_id, playlist_id=playlist_id, radio=radio))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/lyrics/{video_id}")
@app.get("/yt-music/lyrics/{video_id}")
async def ytm_lyrics(video_id: str):
    try:
        return ok(await ytm.get_lyrics(video_id))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/suggestions")
@app.get("/yt-music/suggestions")
async def ytm_suggestions(q: str = Query(..., min_length=1)):
    try:
        return ok(await ytm.suggestions(q))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/moods")
@app.get("/yt-music/moods")
async def ytm_moods():
    try:
        return ok(await ytm.get_moods_and_genres())
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


# ══════════════════════════════════════════════════════════
#  COOKIES
# ══════════════════════════════════════════════════════════
@app.get("/cookies", response_class=HTMLResponse)
async def cookie_ui():
    return COOKIE_HTML


@app.get("/cookies/status")
async def cookie_status():
    return ok(cookies.status())


@app.post("/cookies/upload")
async def cookie_upload(file: UploadFile = File(...)):
    try:
        text = (await file.read()).decode("utf-8", errors="ignore")
        path = cookies.save_netscape(text)
        yt.reload_cookies()
        ytm.reload_cookies()
        return ok({"message": "Cookies saved", "path": str(path), "status": cookies.status()})
    except Exception as e:
        return JSONResponse(status_code=400, content=fail(str(e)))


@app.post("/cookies/paste")
async def cookie_paste(cookie_string: str = Form(...)):
    try:
        path = cookies.save_from_header(cookie_string)
        yt.reload_cookies()
        ytm.reload_cookies()
        return ok({"message": "Cookies saved from header", "path": str(path), "status": cookies.status()})
    except Exception as e:
        return JSONResponse(status_code=400, content=fail(str(e)))


@app.delete("/cookies")
async def cookie_clear():
    cookies.clear()
    yt.reload_cookies()
    ytm.reload_cookies()
    return ok({"message": "Cookies cleared"})


HOME_HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8"/>\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>\n<title>YT Stream API</title>\n<link rel="preconnect" href="https://fonts.googleapis.com"/>\n<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>\n<style>\n:root{\n  --bg:#05080f;\n  --bg2:#0a0f1a;\n  --card:rgba(15,22,36,.85);\n  --card-solid:#0f1624;\n  --border:rgba(148,163,184,.12);\n  --border-h:rgba(99,102,241,.45);\n  --text:#f1f5f9;\n  --muted:#94a3b8;\n  --accent:#6366f1;\n  --accent2:#a855f7;\n  --cyan:#22d3ee;\n  --green:#34d399;\n  --radius:20px;\n  --shadow:0 20px 50px -20px rgba(0,0,0,.6);\n}\n*{box-sizing:border-box;margin:0;padding:0}\nhtml{scroll-behavior:smooth}\nbody{\n  font-family:"DM Sans",system-ui,sans-serif;\n  background:var(--bg);\n  color:var(--text);\n  min-height:100vh;\n  line-height:1.55;\n  -webkit-font-smoothing:antialiased;\n}\nbody::before{\n  content:"";\n  position:fixed;inset:0;z-index:-1;pointer-events:none;\n  background:\n    radial-gradient(ellipse 80% 50% at 20% -10%,rgba(99,102,241,.22),transparent 55%),\n    radial-gradient(ellipse 60% 40% at 90% 10%,rgba(168,85,247,.18),transparent 50%),\n    radial-gradient(ellipse 50% 30% at 50% 100%,rgba(34,211,238,.08),transparent 45%),\n    var(--bg);\n}\n.wrap{max-width:960px;margin:0 auto;padding:48px 20px 100px}\nheader{text-align:center;margin-bottom:48px}\n.logo{\n  display:inline-flex;align-items:center;gap:10px;\n  font-size:.8rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;\n  color:var(--cyan);margin-bottom:16px;\n}\n.logo span{\n  width:8px;height:8px;border-radius:50%;\n  background:linear-gradient(135deg,var(--accent),var(--cyan));\n  box-shadow:0 0 12px var(--accent);\n}\nheader h1{\n  font-size:clamp(1.9rem,5vw,2.6rem);font-weight:700;letter-spacing:-.03em;\n  background:linear-gradient(135deg,#e0e7ff 0%,#a5b4fc 40%,#c084fc 70%,#22d3ee 100%);\n  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;\n}\nheader p{color:var(--muted);margin-top:12px;font-size:1.05rem;max-width:480px;margin-left:auto;margin-right:auto}\n.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px;margin-bottom:36px}\n.card{\n  background:var(--card);backdrop-filter:blur(16px);\n  border:1px solid var(--border);border-radius:var(--radius);\n  padding:24px;box-shadow:var(--shadow);\n  transition:border-color .25s,transform .25s,box-shadow .25s;\n}\n.card:hover{border-color:var(--border-h);transform:translateY(-3px);box-shadow:0 24px 60px -20px rgba(99,102,241,.25)}\n.card .icon{\n  width:42px;height:42px;border-radius:12px;display:flex;align-items:center;justify-content:center;\n  font-size:1.25rem;margin-bottom:14px;\n  background:linear-gradient(135deg,rgba(99,102,241,.2),rgba(168,85,247,.15));\n  border:1px solid rgba(99,102,241,.25);\n}\n.card h3{font-size:1.15rem;font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:8px}\n.badge{\n  font-size:.7rem;font-weight:600;padding:3px 9px;border-radius:999px;\n  background:rgba(99,102,241,.15);color:#a5b4fc;border:1px solid rgba(99,102,241,.25);\n  font-family:"JetBrains Mono",monospace;\n}\n.card p{color:var(--muted);font-size:.9rem;margin-bottom:16px}\n.ep{font-family:"JetBrains Mono",monospace;font-size:.78rem;color:#64748b;margin:5px 0}\n.ep code{color:#93c5fd;background:rgba(30,41,59,.6);padding:2px 7px;border-radius:5px}\n.btn{\n  display:inline-flex;align-items:center;gap:6px;\n  padding:10px 18px;border-radius:999px;font-weight:600;font-size:.88rem;\n  text-decoration:none;color:#fff;border:none;cursor:pointer;\n  background:linear-gradient(135deg,var(--accent),var(--accent2));\n  box-shadow:0 4px 20px rgba(99,102,241,.35);\n  transition:transform .15s,box-shadow .15s;\n}\n.btn:hover{transform:translateY(-1px);box-shadow:0 6px 28px rgba(99,102,241,.45)}\n.btn.ghost{background:transparent;border:1px solid var(--border);color:var(--text);box-shadow:none}\n.btn.ghost:hover{border-color:var(--accent);color:#c7d2fe}\n.actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:4px}\nfooter{text-align:center;color:var(--muted);font-size:.85rem;margin-top:48px}\nfooter a{color:#818cf8;text-decoration:none}\n</style>\n</head>\n<body>\n<div class="wrap">\n  <header>\n    <div class="logo"><span></span> YT Stream</div>\n    <h1>YouTube + Music API</h1>\n    <p>Direct googlevideo CDN streams · yt-dlp · ytmusicapi · LibreTube &amp; SimpMusic style</p>\n  </header>\n\n  <div class="grid">\n    <div class="card">\n      <div class="icon">📺</div>\n      <h3>YouTube <span class="badge">/yt</span></h3>\n      <p>Video streams, search, trending, channels &amp; playlists with direct CDN links.</p>\n      <div class="ep"><code>/yt/streams/{id}</code> → direct_video</div>\n      <div class="ep"><code>/yt/search?q=</code></div>\n      <div class="ep"><code>/yt/trending?region=US</code></div>\n      <div class="actions" style="margin-top:16px">\n        <a class="btn" href="/docs">Open Docs</a>\n      </div>\n    </div>\n\n    <div class="card">\n      <div class="icon">🎵</div>\n      <h3>YouTube Music <span class="badge">/ytm</span></h3>\n      <p>Search, home, charts, artists + high-quality direct audio CDN.</p>\n      <div class="ep"><code>/ytm/play/{id}</code> → audio_url</div>\n      <div class="ep"><code>/ytm/search?q=&amp;filter=songs</code></div>\n      <div class="ep"><code>/ytm/home</code> · <code>/ytm/charts</code></div>\n      <div class="actions" style="margin-top:16px">\n        <a class="btn" href="/docs">Open Docs</a>\n      </div>\n    </div>\n\n    <div class="card">\n      <div class="icon">🍪</div>\n      <h3>Cookies</h3>\n      <p>Unlock age-restricted &amp; Premium quality. Paste cookies from your browser.</p>\n      <div class="actions" style="margin-top:16px">\n        <a class="btn" href="/cookies">Cookie Manager</a>\n      </div>\n    </div>\n\n    <div class="card">\n      <div class="icon">⚡</div>\n      <h3>Status</h3>\n      <p>Health check and interactive API documentation.</p>\n      <div class="actions" style="margin-top:16px">\n        <a class="btn" href="/docs">Swagger</a>\n        <a class="btn ghost" href="/health">Health</a>\n      </div>\n    </div>\n  </div>\n\n  <footer>\n    YT Stream API · v1.2 · <a href="/docs">docs</a>\n  </footer>\n</div>\n</body>\n</html>'

COOKIE_HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8"/>\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>\n<title>Cookie Manager — YT Stream</title>\n<link rel="preconnect" href="https://fonts.googleapis.com"/>\n<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>\n<style>\n:root{\n  --bg:#05080f;--card:rgba(15,22,36,.9);--border:rgba(148,163,184,.12);\n  --text:#f1f5f9;--muted:#94a3b8;--accent:#6366f1;--accent2:#a855f7;\n  --cyan:#22d3ee;--green:#34d399;--red:#f87171;--radius:18px;\n}\n*{box-sizing:border-box;margin:0;padding:0}\nbody{\n  font-family:"DM Sans",system-ui,sans-serif;\n  background:var(--bg);color:var(--text);min-height:100vh;line-height:1.55;\n  -webkit-font-smoothing:antialiased;\n}\nbody::before{\n  content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;\n  background:\n    radial-gradient(ellipse 70% 45% at 15% -5%,rgba(99,102,241,.2),transparent 50%),\n    radial-gradient(ellipse 50% 35% at 95% 5%,rgba(168,85,247,.15),transparent 45%),\n    var(--bg);\n}\n.wrap{max-width:640px;margin:0 auto;padding:36px 18px 90px}\nheader{text-align:center;margin-bottom:28px}\nheader h1{\n  font-size:1.65rem;font-weight:700;letter-spacing:-.02em;\n  background:linear-gradient(135deg,#e0e7ff,#a5b4fc,#c084fc);\n  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;\n}\nheader p{color:var(--muted);margin-top:8px;font-size:.95rem}\n.nav{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin:18px 0 24px}\n.nav a{\n  padding:8px 14px;border-radius:999px;font-size:.84rem;font-weight:500;\n  border:1px solid var(--border);color:var(--muted);text-decoration:none;\n  transition:.2s;\n}\n.nav a:hover{border-color:var(--accent);color:#c7d2fe}\n.badge{\n  display:inline-flex;align-items:center;gap:6px;\n  padding:5px 12px;border-radius:999px;font-size:.8rem;font-weight:600;\n}\n.badge.on{background:rgba(16,185,129,.15);color:var(--green);border:1px solid rgba(52,211,153,.3)}\n.badge.off{background:rgba(239,68,68,.12);color:var(--red);border:1px solid rgba(248,113,113,.25)}\n.card{\n  background:var(--card);backdrop-filter:blur(14px);\n  border:1px solid var(--border);border-radius:var(--radius);\n  padding:22px;margin-bottom:16px;\n  box-shadow:0 16px 40px -16px rgba(0,0,0,.5);\n}\n.card h2{font-size:1.05rem;font-weight:600;margin-bottom:12px;display:flex;align-items:center;gap:8px}\n.steps{list-style:none;counter-reset:s}\n.steps li{\n  counter-increment:s;position:relative;\n  padding:12px 0 12px 44px;border-bottom:1px solid var(--border);\n  color:var(--muted);font-size:.9rem;\n}\n.steps li:last-child{border-bottom:none}\n.steps li::before{\n  content:counter(s);position:absolute;left:0;top:12px;\n  width:28px;height:28px;border-radius:50%;\n  background:linear-gradient(135deg,var(--accent),var(--accent2));\n  color:#fff;font-size:.75rem;font-weight:700;\n  display:flex;align-items:center;justify-content:center;\n}\n.steps strong{color:var(--text)}\n.tabs{display:flex;gap:8px;margin-bottom:14px}\n.tab{\n  flex:1;padding:11px;border-radius:12px;border:1px solid var(--border);\n  background:transparent;color:var(--muted);font-weight:500;font-size:.88rem;\n  cursor:pointer;transition:.2s;\n}\n.tab.active{\n  background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;border-color:transparent;\n  box-shadow:0 4px 16px rgba(99,102,241,.3);\n}\n.panel{display:none}.panel.active{display:block}\ntextarea,input[type=file]{\n  width:100%;background:#080c16;border:1px solid var(--border);\n  border-radius:12px;color:var(--text);padding:14px;\n  font-family:"JetBrains Mono",monospace;font-size:.84rem;margin-bottom:12px;\n}\ntextarea{min-height:130px;resize:vertical}\ntextarea:focus,input:focus{outline:none;border-color:var(--accent)}\n.btn-primary{\n  width:100%;padding:13px;border:none;border-radius:12px;cursor:pointer;\n  font-weight:600;font-size:.95rem;color:#fff;\n  background:linear-gradient(135deg,var(--accent),var(--accent2));\n  box-shadow:0 4px 20px rgba(99,102,241,.35);\n  transition:.15s;\n}\n.btn-primary:hover{transform:translateY(-1px)}\n.btn-primary:disabled{opacity:.45;cursor:not-allowed;transform:none}\n.btn-ghost{\n  width:100%;padding:11px;margin-top:10px;border-radius:12px;cursor:pointer;\n  background:transparent;border:1px solid var(--border);color:var(--muted);font-weight:500;\n}\n.btn-ghost:hover{border-color:var(--red);color:var(--red)}\n.status{margin-top:14px;padding:12px 14px;border-radius:12px;font-size:.88rem;display:none}\n.status.ok{display:block;background:rgba(16,185,129,.12);border:1px solid rgba(52,211,153,.3);color:var(--green)}\n.status.err{display:block;background:rgba(239,68,68,.1);border:1px solid rgba(248,113,113,.25);color:var(--red)}\n.note{\n  margin-top:14px;padding:12px 14px;border-radius:0 12px 12px 0;\n  border-left:3px solid var(--accent2);\n  background:rgba(30,41,59,.4);font-size:.85rem;color:var(--muted);\n}\n.note a{color:#818cf8}\ncode{font-family:"JetBrains Mono",monospace;background:rgba(30,41,59,.7);padding:2px 6px;border-radius:4px;font-size:.8rem}\n.howto-box{\n  background:rgba(99,102,241,.08);border:1px dashed rgba(99,102,241,.35);\n  border-radius:12px;padding:14px;margin-bottom:14px;font-size:.88rem;color:var(--muted);\n}\n.howto-box ol{padding-left:18px;margin-top:8px}\n.howto-box li{margin:6px 0}\n.copy-btn{\n  display:inline-block;margin-top:8px;padding:8px 14px;border-radius:8px;\n  background:rgba(99,102,241,.2);border:1px solid rgba(99,102,241,.4);\n  color:#c7d2fe;font-size:.82rem;font-weight:600;cursor:pointer;\n}\nfooter{text-align:center;color:var(--muted);font-size:.84rem;margin-top:32px}\n</style>\n</head>\n<body>\n<div class="wrap">\n  <header>\n    <h1>🍪 Cookie Manager</h1>\n    <p>Unlock age-restricted content and better audio quality</p>\n    <div style="margin-top:14px"><span id="badge" class="badge off">● Loading…</span></div>\n  </header>\n\n  <div class="nav">\n    <a href="/">Home</a>\n    <a href="/docs">API Docs</a>\n    <a href="/cookies/status">Status JSON</a>\n  </div>\n\n  <div class="card">\n    <h2>How to get cookies (phone or desktop)</h2>\n    <div class="howto-box">\n      <strong style="color:var(--text)">Easiest method — browser extension</strong>\n      <ol>\n        <li>Install <strong>Get cookies.txt LOCALLY</strong> (Chrome / Edge / Brave / Firefox).</li>\n        <li>Open <a href="https://www.youtube.com" target="_blank" rel="noopener">youtube.com</a> or <a href="https://music.youtube.com" target="_blank" rel="noopener">music.youtube.com</a> and log in.</li>\n        <li>Click the extension icon → <strong>Export</strong> → save <code>cookies.txt</code>.</li>\n        <li>Upload that file in the tab below.</li>\n      </ol>\n    </div>\n    <div class="howto-box">\n      <strong style="color:var(--text)">Manual — copy Cookie header</strong>\n      <ol>\n        <li>On desktop: open YouTube → press <code>F12</code> → <strong>Network</strong> tab → reload page.</li>\n        <li>Click any request to <code>youtube.com</code> → Headers → find <code>Cookie:</code>.</li>\n        <li>Copy the entire value (starts with <code>SID=</code> or <code>VISITOR_INFO1_LIVE=</code>).</li>\n        <li>Paste in the <strong>Paste</strong> tab below.</li>\n      </ol>\n      <p style="margin-top:8px">On mobile browsers, use the extension method or desktop DevTools remote debugging.</p>\n    </div>\n    <div class="note">\n      Cookies are tied to your account. Do not share them publicly. They expire — re-export when streams start failing.\n    </div>\n  </div>\n\n  <div class="card">\n    <div class="tabs">\n      <button type="button" class="tab active" data-tab="upload">Upload file</button>\n      <button type="button" class="tab" data-tab="paste">Paste string</button>\n    </div>\n\n    <div id="panel-upload" class="panel active">\n      <input type="file" id="file" accept=".txt,text/plain,*/*"/>\n      <button type="button" class="btn-primary" id="btn-upload">Upload &amp; Save</button>\n    </div>\n\n    <div id="panel-paste" class="panel">\n      <textarea id="cookie-str" placeholder="SID=...; HSID=...; SSID=...; APISID=...; SAPISID=...;&#10;&#10;Or full Netscape cookies.txt content"></textarea>\n      <button type="button" class="btn-primary" id="btn-paste">Save cookies</button>\n    </div>\n\n    <button type="button" class="btn-ghost" id="btn-clear">Clear cookies</button>\n    <div id="msg" class="status"></div>\n  </div>\n\n  <div class="card">\n    <h2>Quick test after saving</h2>\n    <p style="color:var(--muted);font-size:.88rem;margin-bottom:8px">\n      Open these in a new tab — you should see <code>direct_video</code> / <code>audio_url</code> with googlevideo links.\n    </p>\n    <p style="font-family:JetBrains Mono,monospace;font-size:.8rem;color:#64748b">\n      <a href="/yt/streams/dQw4w9WgXcQ" style="color:#93c5fd">/yt/streams/dQw4w9WgXcQ</a><br/>\n      <a href="/ytm/play/dQw4w9WgXcQ" style="color:#93c5fd">/ytm/play/dQw4w9WgXcQ</a>\n    </p>\n  </div>\n\n  <footer>YT Stream API · Cookie Manager</footer>\n</div>\n<script>\n(function(){\n  var badge=document.getElementById("badge");\n  var msg=document.getElementById("msg");\n\n  function show(ok,text){\n    msg.className="status "+(ok?"ok":"err");\n    msg.textContent=text;\n  }\n\n  async function refresh(){\n    try{\n      var r=await fetch("/cookies/status");\n      var j=await r.json();\n      var s=(j&&j.data)||{};\n      if(s.has_cookies){\n        badge.className="badge on";\n        badge.textContent="● Cookies active"+(s.mtime?" · "+s.mtime:"");\n      }else{\n        badge.className="badge off";\n        badge.textContent="● No cookies";\n      }\n    }catch(e){\n      badge.className="badge off";\n      badge.textContent="● Status unavailable";\n    }\n  }\n  refresh();\n\n  document.querySelectorAll(".tab").forEach(function(t){\n    t.addEventListener("click",function(){\n      document.querySelectorAll(".tab").forEach(function(x){x.classList.remove("active");});\n      document.querySelectorAll(".panel").forEach(function(x){x.classList.remove("active");});\n      t.classList.add("active");\n      document.getElementById("panel-"+t.getAttribute("data-tab")).classList.add("active");\n    });\n  });\n\n  document.getElementById("btn-upload").addEventListener("click",async function(){\n    var f=document.getElementById("file").files[0];\n    if(!f){show(false,"Select a cookies.txt file first");return;}\n    var fd=new FormData();\n    fd.append("file",f);\n    var btn=this;btn.disabled=true;\n    try{\n      var r=await fetch("/cookies/upload",{method:"POST",body:fd});\n      var j=await r.json();\n      if(j.ok){show(true,"Cookies saved successfully");refresh();}\n      else show(false,(j.detail&&j.detail.error)||j.error||"Upload failed");\n    }catch(e){show(false,String(e));}\n    finally{btn.disabled=false;}\n  });\n\n  document.getElementById("btn-paste").addEventListener("click",async function(){\n    var v=(document.getElementById("cookie-str").value||"").trim();\n    if(v.length<20){show(false,"Cookie string is too short");return;}\n    var fd=new FormData();\n    fd.append("cookie_string",v);\n    var btn=this;btn.disabled=true;\n    try{\n      var r=await fetch("/cookies/paste",{method:"POST",body:fd});\n      var j=await r.json();\n      if(j.ok){show(true,"Cookies saved from string");refresh();}\n      else show(false,(j.detail&&j.detail.error)||j.error||"Save failed");\n    }catch(e){show(false,String(e));}\n    finally{btn.disabled=false;}\n  });\n\n  document.getElementById("btn-clear").addEventListener("click",async function(){\n    if(!confirm("Clear all saved cookies?"))return;\n    try{\n      var r=await fetch("/cookies",{method:"DELETE"});\n      var j=await r.json();\n      show(!!j.ok,j.ok?"Cookies cleared":"Clear failed");\n      refresh();\n    }catch(e){show(false,String(e));}\n  });\n})();\n</script>\n</body>\n</html>'

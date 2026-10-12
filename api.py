"""
StreamHub YT API — creator: shawon
YouTube + YouTube Music · yt-dlp + ytmusicapi
"""
from __future__ import annotations

import base64
import hashlib
import time
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from youtube_api import YouTubeAPI
from ytm_api import YouTubeMusicAPI
from cookie_manager import CookieManager

# ── identity lock (do not remove) ─────────────────────────
_CREATOR_RAW = "shawon"
_CREATOR_B64 = "c2hhd29u"
_CREATOR_HEX = "736861776f6e"
_CREATOR_SHA = "d29b34b0f159397e"


def _unlock() -> str:
    a = base64.b64decode(_CREATOR_B64.encode()).decode()
    b = bytes.fromhex(_CREATOR_HEX).decode()
    c = _CREATOR_RAW
    if not (a == b == c):
        raise RuntimeError("identity integrity failed")
    h = hashlib.sha256(c.encode()).hexdigest()[:16]
    if h != _CREATOR_SHA:
        raise RuntimeError("identity integrity failed")
    return c


try:
    CREATOR = _unlock()
except Exception:
    CREATOR = ""

VERSION = "1.3.0"
_DEAD = CREATOR != "shawon" or not CREATOR


def _guard() -> None:
    if _DEAD or CREATOR != "shawon":
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "error": "API identity corrupted — creator signature missing",
                "creator": CREATOR or None,
            },
        )


app = FastAPI(
    title=f"StreamHub API · {{CREATOR or '?'}}",
    description="YouTube + YouTube Music API — direct CDN streams",
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

yt = YouTubeAPI()
ytm = YouTubeMusicAPI()
cookies = CookieManager()


def ok(data: Any = None, **extra) -> dict:
    _guard()
    o = {"creator": CREATOR, "ok": True, "version": VERSION}
    if data is not None:
        o["data"] = data
    o.update(extra)
    return o


def fail(msg: str, **extra) -> dict:
    o = {"creator": CREATOR or "unknown", "ok": False, "error": msg, "version": VERSION}
    o.update(extra)
    return o


@app.middleware("http")
async def identity_middleware(request: Request, call_next):
    # soft check every request — hard fail on API routes via ok()/_guard
    if _DEAD and not request.url.path.startswith("/docs"):
        if request.url.path not in ("/", "/cookies"):
            return JSONResponse(
                status_code=503,
                content=fail("API identity corrupted — creator signature missing"),
            )
    return await call_next(request)


@app.get("/", response_class=HTMLResponse)
async def home():
    if _DEAD:
        return HTMLResponse("<h1>API offline — identity lock</h1>", status_code=503)
    return HOME_HTML


@app.get("/health")
async def health():
    _guard()
    return ok({"status": "alive", "ts": int(time.time()), "cookies": cookies.status(), "creator": CREATOR})


# ── YouTube ───────────────────────────────────────────────
@app.get("/yt/streams/{video_id}")
@app.get("/youtube/streams/{video_id}")
async def yt_streams(video_id: str):
    _guard()
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
async def yt_search(q: str = Query(..., min_length=1), filter: str = Query("all"), limit: int = Query(20, ge=1, le=50)):
    _guard()
    try:
        return ok(await yt.search(q, filter=filter, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/trending")
@app.get("/youtube/trending")
async def yt_trending(region: str = Query("US", min_length=2, max_length=2), category: str = Query("default")):
    _guard()
    try:
        return ok(await yt.trending(region=region.upper(), category=category))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/channel/{channel_id}")
@app.get("/youtube/channel/{channel_id}")
async def yt_channel(channel_id: str, limit: int = Query(20, ge=1, le=50)):
    _guard()
    try:
        return ok(await yt.get_channel(channel_id, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/playlist/{playlist_id}")
@app.get("/youtube/playlist/{playlist_id}")
async def yt_playlist(playlist_id: str, limit: int = Query(50, ge=1, le=100)):
    _guard()
    try:
        return ok(await yt.get_playlist(playlist_id, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/comments/{video_id}")
@app.get("/youtube/comments/{video_id}")
async def yt_comments(video_id: str, limit: int = Query(30, ge=1, le=100)):
    _guard()
    try:
        return ok(await yt.get_comments(video_id, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/suggestions")
@app.get("/youtube/suggestions")
async def yt_suggestions(q: str = Query(..., min_length=1)):
    _guard()
    try:
        return ok(await yt.suggestions(q))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/info")
@app.get("/youtube/info")
async def yt_info(url: str = Query(...)):
    _guard()
    try:
        return ok(await yt.extract_info(url))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


# ── YouTube Music ─────────────────────────────────────────
@app.get("/ytm/search")
@app.get("/yt-music/search")
@app.get("/music/search")
async def ytm_search(q: str = Query(..., min_length=1), filter: str = Query("songs"), limit: int = Query(20, ge=1, le=50)):
    _guard()
    try:
        return ok(await ytm.search(q, filter=filter, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/home")
@app.get("/yt-music/home")
async def ytm_home(limit: int = Query(6, ge=1, le=12)):
    _guard()
    try:
        return ok(await ytm.home(limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/charts")
@app.get("/yt-music/charts")
async def ytm_charts(country: str = Query("ZZ")):
    _guard()
    try:
        return ok(await ytm.charts(country=country.upper()))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/artist/{artist_id}")
@app.get("/yt-music/artist/{artist_id}")
async def ytm_artist(artist_id: str):
    _guard()
    try:
        return ok(await ytm.get_artist(artist_id))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/album/{browse_id}")
@app.get("/yt-music/album/{browse_id}")
async def ytm_album(browse_id: str):
    _guard()
    try:
        return ok(await ytm.get_album(browse_id))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/playlist/{playlist_id}")
@app.get("/yt-music/playlist/{playlist_id}")
async def ytm_playlist(playlist_id: str, limit: int = Query(100, ge=1, le=200)):
    _guard()
    try:
        return ok(await ytm.get_playlist(playlist_id, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/play/{video_id}")
@app.get("/yt-music/play/{video_id}")
@app.get("/music/play/{video_id}")
async def ytm_play(video_id: str):
    _guard()
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
async def ytm_next(video_id: str = Query(...), playlist_id: Optional[str] = Query(None), radio: bool = Query(True)):
    _guard()
    try:
        return ok(await ytm.get_watch_playlist(video_id, playlist_id=playlist_id, radio=radio))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/lyrics/{video_id}")
@app.get("/yt-music/lyrics/{video_id}")
async def ytm_lyrics(video_id: str):
    _guard()
    try:
        return ok(await ytm.get_lyrics(video_id))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/suggestions")
@app.get("/yt-music/suggestions")
async def ytm_suggestions(q: str = Query(..., min_length=1)):
    _guard()
    try:
        return ok(await ytm.suggestions(q))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/moods")
@app.get("/yt-music/moods")
async def ytm_moods():
    _guard()
    try:
        return ok(await ytm.get_moods_and_genres())
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


# ── Cookies ───────────────────────────────────────────────
@app.get("/cookies", response_class=HTMLResponse)
async def cookie_ui():
    if _DEAD:
        return HTMLResponse("<h1>API offline</h1>", status_code=503)
    return COOKIE_HTML


@app.get("/cookies/status")
async def cookie_status():
    _guard()
    return ok(cookies.status())


@app.post("/cookies/upload")
async def cookie_upload(file: UploadFile = File(...)):
    _guard()
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
    _guard()
    try:
        path = cookies.save_from_header(cookie_string)
        yt.reload_cookies()
        ytm.reload_cookies()
        return ok({"message": "Cookies saved", "path": str(path), "status": cookies.status()})
    except Exception as e:
        return JSONResponse(status_code=400, content=fail(str(e)))


@app.delete("/cookies")
async def cookie_clear():
    _guard()
    cookies.clear()
    yt.reload_cookies()
    ytm.reload_cookies()
    return ok({"message": "Cookies cleared"})


HOME_HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8"/>\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>\n<title>StreamHub · shawon</title>\n<link rel="preconnect" href="https://fonts.googleapis.com"/>\n<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;600;700&family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>\n<style>\n:root{\n  --bg:#030712;\n  --panel:rgba(8,12,24,.72);\n  --line:rgba(56,189,248,.14);\n  --line2:rgba(167,139,250,.22);\n  --text:#f8fafc;\n  --muted:#94a3b8;\n  --c1:#22d3ee;\n  --c2:#a78bfa;\n  --c3:#f472b6;\n  --ok:#34d399;\n  --r:22px;\n}\n*{box-sizing:border-box;margin:0;padding:0}\nhtml,body{height:100%}\nbody{\n  font-family:"Outfit",system-ui,sans-serif;\n  background:var(--bg);color:var(--text);\n  min-height:100vh;line-height:1.5;\n  -webkit-font-smoothing:antialiased;\n  overflow-x:hidden;\n}\n/* futuristic grid + glow */\n.fx{\n  position:fixed;inset:0;z-index:-1;pointer-events:none;\n  background:\n    radial-gradient(900px 500px at 12% -8%,rgba(34,211,238,.16),transparent 55%),\n    radial-gradient(700px 420px at 92% 8%,rgba(167,139,250,.14),transparent 50%),\n    radial-gradient(600px 380px at 50% 110%,rgba(244,114,182,.08),transparent 50%),\n    linear-gradient(180deg,#030712 0%,#050a14 100%);\n}\n.fx::after{\n  content:"";position:absolute;inset:0;\n  background-image:\n    linear-gradient(rgba(34,211,238,.04) 1px,transparent 1px),\n    linear-gradient(90deg,rgba(34,211,238,.04) 1px,transparent 1px);\n  background-size:48px 48px;\n  mask-image:radial-gradient(ellipse 70% 60% at 50% 30%,#000 20%,transparent 75%);\n}\n.wrap{max-width:1000px;margin:0 auto;padding:28px 18px 120px}\n\n/* sticky top bar */\n.top{\n  position:sticky;top:0;z-index:50;\n  margin:-28px -18px 28px;padding:14px 18px;\n  background:rgba(3,7,18,.78);\n  backdrop-filter:blur(18px) saturate(1.4);\n  border-bottom:1px solid var(--line);\n  display:flex;align-items:center;justify-content:space-between;gap:12px;\n}\n.brand{\n  display:flex;align-items:center;gap:10px;\n  font-family:"Orbitron",sans-serif;font-weight:600;font-size:.92rem;\n  letter-spacing:.06em;text-transform:uppercase;\n}\n.brand .dot{\n  width:10px;height:10px;border-radius:50%;\n  background:linear-gradient(135deg,var(--c1),var(--c2));\n  box-shadow:0 0 16px var(--c1),0 0 32px rgba(34,211,238,.35);\n  animation:pulse 2.4s ease-in-out infinite;\n}\n@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.65;transform:scale(.85)}}\n.brand em{font-style:normal;color:var(--c1)}\n.top nav{display:flex;gap:8px;flex-wrap:wrap}\n.top a{\n  text-decoration:none;color:var(--muted);font-size:.82rem;font-weight:500;\n  padding:7px 12px;border-radius:999px;border:1px solid transparent;\n  transition:.2s;\n}\n.top a:hover{color:var(--text);border-color:var(--line);background:rgba(34,211,238,.06)}\n\nheader{text-align:center;padding:24px 0 36px}\nheader h1{\n  font-family:"Orbitron",sans-serif;\n  font-size:clamp(1.7rem,5.5vw,2.5rem);font-weight:700;letter-spacing:.02em;\n  background:linear-gradient(120deg,#e0f2fe 0%,var(--c1) 35%,var(--c2) 70%,var(--c3) 100%);\n  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;\n}\nheader p{color:var(--muted);margin-top:12px;font-size:1.02rem;max-width:520px;margin-left:auto;margin-right:auto}\n.chip{\n  display:inline-flex;align-items:center;gap:6px;margin-top:16px;\n  padding:6px 14px;border-radius:999px;font-size:.78rem;font-weight:600;\n  border:1px solid var(--line);background:rgba(34,211,238,.06);color:var(--c1);\n  font-family:"JetBrains Mono",monospace;\n}\n\n.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px}\n.card{\n  position:relative;\n  background:var(--panel);backdrop-filter:blur(16px);\n  border:1px solid var(--line);border-radius:var(--r);\n  padding:22px 20px;overflow:hidden;\n  transition:transform .25s,border-color .25s,box-shadow .25s;\n}\n.card::before{\n  content:"";position:absolute;inset:-1px;border-radius:inherit;padding:1px;\n  background:linear-gradient(135deg,rgba(34,211,238,.35),transparent 40%,transparent 60%,rgba(167,139,250,.3));\n  -webkit-mask:linear-gradient(#fff 0 0) content-box,linear-gradient(#fff 0 0);\n  mask:linear-gradient(#fff 0 0) content-box,linear-gradient(#fff 0 0);\n  -webkit-mask-composite:xor;mask-composite:exclude;\n  opacity:0;transition:opacity .25s;pointer-events:none;\n}\n.card:hover{transform:translateY(-4px);border-color:var(--line2);box-shadow:0 24px 50px -24px rgba(34,211,238,.25)}\n.card:hover::before{opacity:1}\n.ico{\n  width:44px;height:44px;border-radius:14px;display:grid;place-items:center;\n  font-size:1.3rem;margin-bottom:14px;\n  background:linear-gradient(145deg,rgba(34,211,238,.12),rgba(167,139,250,.1));\n  border:1px solid rgba(34,211,238,.2);\n}\n.card h3{font-size:1.12rem;font-weight:600;margin-bottom:6px;display:flex;align-items:center;gap:8px}\n.badge{\n  font-size:.68rem;font-weight:600;padding:3px 8px;border-radius:999px;\n  background:rgba(167,139,250,.12);color:#c4b5fd;border:1px solid rgba(167,139,250,.25);\n  font-family:"JetBrains Mono",monospace;\n}\n.card p{color:var(--muted);font-size:.9rem;margin-bottom:14px}\n.ep{font-family:"JetBrains Mono",monospace;font-size:.76rem;color:#64748b;margin:4px 0}\n.ep code{color:#7dd3fc;background:rgba(15,23,42,.7);padding:2px 6px;border-radius:5px}\n.btn{\n  display:inline-flex;align-items:center;gap:6px;margin-top:8px;\n  padding:10px 16px;border-radius:999px;font-weight:600;font-size:.86rem;\n  text-decoration:none;color:#031016;border:none;cursor:pointer;\n  background:linear-gradient(135deg,var(--c1),#67e8f9);\n  box-shadow:0 0 24px rgba(34,211,238,.25);\n  transition:.2s;\n}\n.btn:hover{transform:translateY(-1px);box-shadow:0 0 32px rgba(34,211,238,.4)}\n.btn.alt{\n  color:var(--text);\n  background:transparent;border:1px solid var(--line);\n  box-shadow:none;margin-left:8px;\n}\n.btn.alt:hover{border-color:var(--c2);color:#e9d5ff}\nfooter{\n  text-align:center;margin-top:48px;padding-top:20px;\n  border-top:1px solid var(--line);color:var(--muted);font-size:.84rem;\n}\nfooter strong{color:var(--c1);font-family:"Orbitron",sans-serif;font-weight:600;letter-spacing:.04em}\n</style>\n</head>\n<body>\n<div class="fx"></div>\n<div class="wrap">\n  <div class="top">\n    <div class="brand"><span class="dot"></span> STREAM<em>HUB</em></div>\n    <nav>\n      <a href="/docs">Docs</a>\n      <a href="/cookies">Cookies</a>\n      <a href="/health">Health</a>\n    </nav>\n  </div>\n\n  <header>\n    <h1>YouTube + Music API</h1>\n    <p>Direct googlevideo CDN · yt-dlp · ytmusicapi · built for speed</p>\n    <div class="chip">creator · shawon</div>\n  </header>\n\n  <div class="grid">\n    <div class="card">\n      <div class="ico">📺</div>\n      <h3>YouTube <span class="badge">/yt</span></h3>\n      <p>Streams, search, trending, channels — direct CDN links.</p>\n      <div class="ep"><code>/yt/streams/{id}</code></div>\n      <div class="ep"><code>/yt/search?q=</code></div>\n      <a class="btn" href="/docs">Open docs</a>\n    </div>\n    <div class="card">\n      <div class="ico">🎵</div>\n      <h3>YouTube Music <span class="badge">/ytm</span></h3>\n      <p>Home, charts, artists + high-quality audio CDN.</p>\n      <div class="ep"><code>/ytm/play/{id}</code></div>\n      <div class="ep"><code>/ytm/search?q=</code></div>\n      <a class="btn" href="/docs">Open docs</a>\n    </div>\n    <div class="card">\n      <div class="ico">🍪</div>\n      <h3>Cookies</h3>\n      <p>One paste. Unlock restricted &amp; premium quality.</p>\n      <a class="btn" href="/cookies">Cookie vault</a>\n    </div>\n    <div class="card">\n      <div class="ico">⚡</div>\n      <h3>Live status</h3>\n      <p>Health + interactive Swagger for every route.</p>\n      <a class="btn" href="/health">Health</a>\n      <a class="btn alt" href="/docs">Swagger</a>\n    </div>\n  </div>\n\n  <footer>\n    Powered by <strong>shawon</strong> · StreamHub API\n  </footer>\n</div>\n</body>\n</html>'

COOKIE_HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8"/>\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>\n<title>Cookie Vault · shawon</title>\n<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;600;700&family=Outfit:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>\n<style>\n:root{\n  --bg:#030712;--panel:rgba(8,12,24,.8);--line:rgba(56,189,248,.14);\n  --text:#f8fafc;--muted:#94a3b8;--c1:#22d3ee;--c2:#a78bfa;--ok:#34d399;--err:#f87171;--r:18px;\n}\n*{box-sizing:border-box;margin:0;padding:0}\nbody{font-family:"Outfit",system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;line-height:1.5}\nbody::before{\n  content:"";position:fixed;inset:0;z-index:-1;\n  background:\n    radial-gradient(700px 400px at 10% -5%,rgba(34,211,238,.14),transparent 50%),\n    radial-gradient(500px 320px at 100% 0%,rgba(167,139,250,.12),transparent 45%),\n    var(--bg);\n}\n.wrap{max-width:560px;margin:0 auto;padding:0 16px 100px}\n.top{\n  position:sticky;top:0;z-index:40;\n  margin:0 -16px 20px;padding:12px 16px;\n  background:rgba(3,7,18,.82);backdrop-filter:blur(16px);\n  border-bottom:1px solid var(--line);\n  display:flex;align-items:center;justify-content:space-between;\n}\n.brand{font-family:"Orbitron",sans-serif;font-size:.8rem;font-weight:600;letter-spacing:.06em;color:var(--c1)}\n.top a{color:var(--muted);text-decoration:none;font-size:.82rem;margin-left:12px}\n.top a:hover{color:var(--text)}\nheader{text-align:center;padding:12px 0 20px}\nheader h1{\n  font-family:"Orbitron",sans-serif;font-size:1.35rem;font-weight:700;\n  background:linear-gradient(120deg,#e0f2fe,var(--c1),var(--c2));\n  -webkit-background-clip:text;-webkit-text-fill-color:transparent;\n}\nheader p{color:var(--muted);font-size:.9rem;margin-top:6px}\n.badge{display:inline-flex;gap:6px;align-items:center;margin-top:12px;padding:5px 12px;border-radius:999px;font-size:.78rem;font-weight:600}\n.badge.on{background:rgba(52,211,153,.12);color:var(--ok);border:1px solid rgba(52,211,153,.3)}\n.badge.off{background:rgba(248,113,113,.1);color:var(--err);border:1px solid rgba(248,113,113,.25)}\n.card{\n  background:var(--panel);border:1px solid var(--line);border-radius:var(--r);\n  padding:18px;margin-bottom:14px;backdrop-filter:blur(12px);\n}\n.card h2{font-size:.98rem;font-weight:600;margin-bottom:10px}\n.easy{\n  background:linear-gradient(135deg,rgba(34,211,238,.08),rgba(167,139,250,.06));\n  border:1px solid rgba(34,211,238,.22);border-radius:14px;padding:14px;margin-bottom:12px;\n}\n.easy strong{display:block;color:var(--c1);font-size:.88rem;margin-bottom:6px}\n.easy ol{padding-left:18px;color:var(--muted);font-size:.86rem}\n.easy li{margin:5px 0}\n.easy a{color:#7dd3fc}\n.tabs{display:flex;gap:8px;margin-bottom:12px}\n.tab{\n  flex:1;padding:11px;border-radius:12px;border:1px solid var(--line);\n  background:transparent;color:var(--muted);font-weight:600;font-size:.86rem;cursor:pointer;\n}\n.tab.active{background:linear-gradient(135deg,#0891b2,#7c3aed);color:#fff;border-color:transparent}\n.panel{display:none}.panel.active{display:block}\ntextarea,input[type=file]{\n  width:100%;background:#020617;border:1px solid var(--line);border-radius:12px;\n  color:var(--text);padding:12px;font-family:"JetBrains Mono",monospace;font-size:.82rem;margin-bottom:10px;\n}\ntextarea{min-height:120px;resize:vertical}\ntextarea:focus{outline:none;border-color:var(--c1)}\n.btn{\n  width:100%;padding:13px;border:none;border-radius:12px;cursor:pointer;\n  font-weight:700;font-size:.92rem;color:#031016;\n  background:linear-gradient(135deg,var(--c1),#67e8f9);\n  box-shadow:0 0 24px rgba(34,211,238,.22);\n}\n.btn:disabled{opacity:.45}\n.btn-g{width:100%;margin-top:8px;padding:11px;border-radius:12px;background:transparent;border:1px solid var(--line);color:var(--muted);cursor:pointer}\n.btn-g:hover{border-color:var(--err);color:var(--err)}\n.msg{margin-top:12px;padding:11px;border-radius:10px;font-size:.86rem;display:none}\n.msg.ok{display:block;background:rgba(52,211,153,.1);border:1px solid rgba(52,211,153,.3);color:var(--ok)}\n.msg.err{display:block;background:rgba(248,113,113,.08);border:1px solid rgba(248,113,113,.25);color:var(--err)}\n.hint{font-size:.8rem;color:var(--muted);margin-top:8px}\nfooter{text-align:center;margin-top:28px;color:var(--muted);font-size:.8rem}\nfooter b{color:var(--c1);font-family:Orbitron,sans-serif}\n</style>\n</head>\n<body>\n<div class="wrap">\n  <div class="top">\n    <div class="brand">SHAWON · VAULT</div>\n    <div><a href="/">Home</a><a href="/docs">Docs</a></div>\n  </div>\n  <header>\n    <h1>Cookie Vault</h1>\n    <p>Paste once — unlock full streams</p>\n    <div><span id="badge" class="badge off">● Loading…</span></div>\n  </header>\n\n  <div class="card">\n    <h2>Easiest way (2 minutes)</h2>\n    <div class="easy">\n      <strong>Phone or PC</strong>\n      <ol>\n        <li>Install extension: <b>Get cookies.txt LOCALLY</b></li>\n        <li>Open <a href="https://youtube.com" target="_blank" rel="noopener">youtube.com</a> → log in</li>\n        <li>Tap extension → <b>Export</b> → get <code>cookies.txt</code></li>\n        <li>Upload below (or paste file contents)</li>\n      </ol>\n    </div>\n    <div class="easy">\n      <strong>Desktop only — no extension</strong>\n      <ol>\n        <li>YouTube → <code>F12</code> → Network → reload</li>\n        <li>Click any youtube request → Headers → <code>Cookie</code></li>\n        <li>Copy full value → Paste tab</li>\n      </ol>\n    </div>\n  </div>\n\n  <div class="card">\n    <div class="tabs">\n      <button type="button" class="tab active" data-tab="upload">Upload</button>\n      <button type="button" class="tab" data-tab="paste">Paste</button>\n    </div>\n    <div id="panel-upload" class="panel active">\n      <input type="file" id="file" accept=".txt,text/plain,*/*"/>\n      <button type="button" class="btn" id="btn-up">Save cookies</button>\n    </div>\n    <div id="panel-paste" class="panel">\n      <textarea id="txt" placeholder="Paste Cookie header (SID=...) or full cookies.txt here"></textarea>\n      <button type="button" class="btn" id="btn-paste">Save cookies</button>\n      <p class="hint">Accepts Cookie header OR full Netscape cookies.txt text.</p>\n    </div>\n    <button type="button" class="btn-g" id="btn-clear">Clear saved cookies</button>\n    <div id="msg" class="msg"></div>\n  </div>\n\n  <div class="card">\n    <h2>Test after save</h2>\n    <p class="hint">\n      <a href="/yt/streams/dQw4w9WgXcQ" style="color:#7dd3fc">/yt/streams/…</a><br/>\n      <a href="/ytm/play/dQw4w9WgXcQ" style="color:#7dd3fc">/ytm/play/…</a>\n    </p>\n  </div>\n  <footer>Locked to <b>shawon</b></footer>\n</div>\n<script>\n(function(){\n  var badge=document.getElementById("badge"),msg=document.getElementById("msg");\n  function show(ok,t){msg.className="msg "+(ok?"ok":"err");msg.textContent=t;}\n  async function refresh(){\n    try{\n      var j=await(await fetch("/cookies/status")).json();\n      var s=j.data||{};\n      if(s.has_cookies){badge.className="badge on";badge.textContent="● Active"+(s.mtime?" · "+s.mtime:"");}\n      else{badge.className="badge off";badge.textContent="● No cookies";}\n    }catch(e){badge.className="badge off";badge.textContent="● Offline";}\n  }\n  refresh();\n  document.querySelectorAll(".tab").forEach(function(t){\n    t.onclick=function(){\n      document.querySelectorAll(".tab").forEach(function(x){x.classList.remove("active");});\n      document.querySelectorAll(".panel").forEach(function(x){x.classList.remove("active");});\n      t.classList.add("active");\n      document.getElementById("panel-"+t.dataset.tab).classList.add("active");\n    };\n  });\n  document.getElementById("btn-up").onclick=async function(){\n    var f=document.getElementById("file").files[0];\n    if(!f)return show(false,"Choose a cookies.txt file");\n    var fd=new FormData();fd.append("file",f);\n    this.disabled=true;\n    try{\n      var j=await(await fetch("/cookies/upload",{method:"POST",body:fd})).json();\n      if(j.ok){show(true,"Saved");refresh();}else show(false,j.error||"Failed");\n    }catch(e){show(false,String(e));}\n    this.disabled=false;\n  };\n  document.getElementById("btn-paste").onclick=async function(){\n    var v=(document.getElementById("txt").value||"").trim();\n    if(v.length<20)return show(false,"Paste is too short");\n    var fd=new FormData();fd.append("cookie_string",v);\n    this.disabled=true;\n    try{\n      var j=await(await fetch("/cookies/paste",{method:"POST",body:fd})).json();\n      if(j.ok){show(true,"Saved");refresh();}else show(false,j.error||"Failed");\n    }catch(e){show(false,String(e));}\n    this.disabled=false;\n  };\n  document.getElementById("btn-clear").onclick=async function(){\n    if(!confirm("Clear cookies?"))return;\n    try{\n      var j=await(await fetch("/cookies",{method:"DELETE"})).json();\n      show(!!j.ok,j.ok?"Cleared":"Failed");refresh();\n    }catch(e){show(false,String(e));}\n  };\n})();\n</script>\n</body>\n</html>'

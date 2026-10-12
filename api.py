"""StreamHub YT API — creator: shawon"""
from __future__ import annotations

import base64
import hashlib
import time
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from youtube_api import YouTubeAPI
from ytm_api import YouTubeMusicAPI
from cookie_manager import CookieManager

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

VERSION = "1.5.0"
_DEAD = CREATOR != "shawon" or not CREATOR


def _guard() -> None:
    if _DEAD or CREATOR != "shawon":
        raise HTTPException(
            status_code=503,
            detail={"ok": False, "error": "API identity corrupted", "creator": CREATOR or None},
        )


app = FastAPI(
    title="StreamHub API · shawon",
    description="YouTube + YouTube Music — direct CDN streams & downloads",
    version=VERSION,
    docs_url=None,
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
    if _DEAD and request.url.path not in ("/", "/cookies", "/docs", "/openapi.json", "/redoc"):
        return JSONResponse(status_code=503, content=fail("API identity corrupted"))
    return await call_next(request)


@app.get("/docs", include_in_schema=False)
async def swagger_ui():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="StreamHub API · shawon",
        swagger_ui_parameters={"docExpansion": "none", "defaultModelsExpandDepth": -1},
        swagger_favicon_url="https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/svg/1f3b5.svg",
    )


@app.get("/", response_class=HTMLResponse)
async def home():
    if _DEAD:
        return HTMLResponse("<h1>API offline</h1>", status_code=503)
    return HOME_HTML


@app.get("/health")
async def health():
    _guard()
    return ok({"status": "alive", "ts": int(time.time()), "cookies": cookies.status(), "creator": CREATOR})


# ── YouTube ───────────────────────────────────────────────
@app.get("/yt/streams/{video_id}")
async def yt_streams(video_id: str):
    """Direct CDN video + audio streams."""
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


@app.get("/yt/download/{video_id}")
async def yt_download(
    video_id: str,
    quality: str = Query("best", description="best | 1080 | 720 | 480 | 360 | audio"),
):
    """Best video or audio download URL (direct CDN)."""
    _guard()
    try:
        data = await yt.get_streams(video_id)
        q = (quality or "best").lower()
        if q in ("audio", "mp3", "m4a"):
            url = data.get("direct_audio") or data.get("direct_play")
            return ok({
                "videoId": data.get("videoId"),
                "title": data.get("title"),
                "type": "audio",
                "url": url,
                "provider": data.get("provider"),
            })
        url = data.get("direct_video") or data.get("direct_play")
        if q.isdigit():
            h = int(q)
            for item in data.get("qualities") or []:
                if (item.get("height") or 0) <= h and (item.get("url") or item.get("video_url")):
                    url = item.get("url") or item.get("video_url")
                    break
        return ok({
            "videoId": data.get("videoId"),
            "title": data.get("title"),
            "type": "video",
            "url": url,
            "direct_video": data.get("direct_video"),
            "direct_audio": data.get("direct_audio"),
            "provider": data.get("provider"),
        })
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/search")
async def yt_search(q: str = Query(..., min_length=1), filter: str = Query("all"), limit: int = Query(20, ge=1, le=50)):
    _guard()
    try:
        return ok(await yt.search(q, filter=filter, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/trending")
async def yt_trending(region: str = Query("US", min_length=2, max_length=2), category: str = Query("default")):
    _guard()
    try:
        return ok(await yt.trending(region=region.upper(), category=category))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/channel/{channel_id}")
async def yt_channel(channel_id: str, limit: int = Query(20, ge=1, le=50)):
    _guard()
    try:
        return ok(await yt.get_channel(channel_id, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/playlist/{playlist_id}")
async def yt_playlist(playlist_id: str, limit: int = Query(50, ge=1, le=100)):
    _guard()
    try:
        return ok(await yt.get_playlist(playlist_id, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/comments/{video_id}")
async def yt_comments(video_id: str, limit: int = Query(30, ge=1, le=100)):
    _guard()
    try:
        return ok(await yt.get_comments(video_id, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/suggestions")
async def yt_suggestions(q: str = Query(..., min_length=1)):
    _guard()
    try:
        return ok(await yt.suggestions(q))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/info")
async def yt_info(url: str = Query(...)):
    _guard()
    try:
        return ok(await yt.extract_info(url))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


# ── YouTube Music ─────────────────────────────────────────
@app.get("/ytm/search")
async def ytm_search(q: str = Query(..., min_length=1), filter: str = Query("songs"), limit: int = Query(20, ge=1, le=50)):
    _guard()
    try:
        return ok(await ytm.search(q, filter=filter, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/home")
async def ytm_home(limit: int = Query(6, ge=1, le=12)):
    _guard()
    try:
        return ok(await ytm.home(limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/charts")
async def ytm_charts(country: str = Query("ZZ")):
    _guard()
    try:
        return ok(await ytm.charts(country=country.upper()))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/artist/{artist_id}")
async def ytm_artist(artist_id: str):
    _guard()
    try:
        return ok(await ytm.get_artist(artist_id))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/album/{browse_id}")
async def ytm_album(browse_id: str):
    _guard()
    try:
        return ok(await ytm.get_album(browse_id))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/playlist/{playlist_id}")
async def ytm_playlist(playlist_id: str, limit: int = Query(100, ge=1, le=200)):
    _guard()
    try:
        return ok(await ytm.get_playlist(playlist_id, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/play/{video_id}")
async def ytm_play(video_id: str):
    """Direct audio CDN URL for a track."""
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


@app.get("/ytm/download/{video_id}")
async def ytm_download(video_id: str):
    """YouTube Music audio download URL."""
    _guard()
    try:
        data = await ytm.play(video_id)
        url = data.get("audio_url") or data.get("directUrl")
        if not url:
            raise HTTPException(502, detail=fail("No audio URL", videoId=video_id))
        return ok({
            "videoId": data.get("videoId"),
            "title": data.get("title"),
            "artist": data.get("artist"),
            "type": "audio",
            "url": url,
            "provider": data.get("provider"),
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/next")
async def ytm_next(video_id: str = Query(...), playlist_id: Optional[str] = Query(None), radio: bool = Query(True)):
    _guard()
    try:
        return ok(await ytm.get_watch_playlist(video_id, playlist_id=playlist_id, radio=radio))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/lyrics/{video_id}")
async def ytm_lyrics(video_id: str):
    _guard()
    try:
        return ok(await ytm.get_lyrics(video_id))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/suggestions")
async def ytm_suggestions(q: str = Query(..., min_length=1)):
    _guard()
    try:
        return ok(await ytm.suggestions(q))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/moods")
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


HOME_HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>\n<title>StreamHub · shawon</title>\n<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700&family=Outfit:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>\n<style>\n:root{--bg:#020617;--card:rgba(15,23,42,.75);--line:rgba(56,189,248,.18);--t:#f8fafc;--m:#94a3b8;--c:#22d3ee;--p:#a78bfa;--pk:#f472b6}\n*{box-sizing:border-box;margin:0;padding:0}\nbody{font-family:Outfit,system-ui,sans-serif;background:var(--bg);color:var(--t);min-height:100vh}\nbody::before{content:"";position:fixed;inset:0;z-index:-1;background:\n radial-gradient(800px 480px at 10% -10%,rgba(34,211,238,.18),transparent 55%),\n radial-gradient(600px 400px at 95% 5%,rgba(167,139,250,.14),transparent 50%),\n linear-gradient(180deg,#020617,#0a0f1e)}\n.wrap{max-width:980px;margin:0 auto;padding:0 16px 100px}\n.top{position:sticky;top:0;z-index:40;margin:0 -16px 24px;padding:12px 16px;display:flex;align-items:center;justify-content:space-between;\n background:rgba(2,6,23,.82);backdrop-filter:blur(16px);border-bottom:1px solid var(--line)}\n.brand{font-family:Orbitron,sans-serif;font-size:.85rem;letter-spacing:.06em;color:var(--c)}\n.top a{color:var(--m);text-decoration:none;font-size:.82rem;margin-left:10px;padding:6px 10px;border-radius:999px;border:1px solid transparent}\n.top a:hover{color:var(--t);border-color:var(--line)}\nheader{text-align:center;padding:28px 0 32px}\nh1{font-family:Orbitron,sans-serif;font-size:clamp(1.6rem,5vw,2.4rem);background:linear-gradient(120deg,#e0f2fe,var(--c),var(--p),var(--pk));-webkit-background-clip:text;-webkit-text-fill-color:transparent}\nheader p{color:var(--m);margin-top:10px}\n.chip{display:inline-block;margin-top:14px;padding:5px 12px;border-radius:999px;font-size:.75rem;font-family:JetBrains Mono,monospace;border:1px solid var(--line);color:var(--c);background:rgba(34,211,238,.06)}\n.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}\n.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px;backdrop-filter:blur(12px);transition:.2s}\n.card:hover{transform:translateY(-3px);border-color:rgba(167,139,250,.4);box-shadow:0 20px 40px -24px rgba(34,211,238,.35)}\n.ico{width:40px;height:40px;border-radius:12px;display:grid;place-items:center;margin-bottom:12px;background:rgba(34,211,238,.1);border:1px solid rgba(34,211,238,.2)}\n.card h3{font-size:1.05rem;margin-bottom:6px}\n.card p{color:var(--m);font-size:.88rem;margin-bottom:12px}\ncode{font-family:JetBrains Mono,monospace;font-size:.74rem;color:#7dd3fc;background:rgba(15,23,42,.8);padding:2px 6px;border-radius:5px}\n.btn{display:inline-block;margin-top:8px;padding:9px 14px;border-radius:999px;background:linear-gradient(135deg,var(--c),#67e8f9);color:#022;text-decoration:none;font-weight:700;font-size:.84rem}\nfooter{text-align:center;margin-top:40px;color:var(--m);font-size:.82rem;border-top:1px solid var(--line);padding-top:18px}\nfooter b{color:var(--c);font-family:Orbitron,sans-serif}\n</style></head>\n<body>\n<div class="wrap">\n  <div class="top">\n    <div class="brand">STREAMHUB</div>\n    <div><a href="/docs">Docs</a><a href="/cookies">Cookies</a><a href="/health">Health</a></div>\n  </div>\n  <header>\n    <h1>YouTube + Music API</h1>\n    <p>Direct CDN streams · download · search · charts</p>\n    <div class="chip">creator · shawon · v1.5.0</div>\n  </header>\n  <div class="grid">\n    <div class="card"><div class="ico">📺</div><h3>YouTube</h3><p>Streams &amp; download with direct CDN links.</p>\n      <div><code>/yt/streams/{id}</code></div><div><code>/yt/download/{id}</code></div>\n      <a class="btn" href="/docs">Open docs</a></div>\n    <div class="card"><div class="ico">🎵</div><h3>YouTube Music</h3><p>Play &amp; audio download URLs.</p>\n      <div><code>/ytm/play/{id}</code></div><div><code>/ytm/download/{id}</code></div>\n      <a class="btn" href="/docs">Open docs</a></div>\n    <div class="card"><div class="ico">🍪</div><h3>Cookies</h3><p>Optional — improves restricted content.</p>\n      <a class="btn" href="/cookies">Cookie vault</a></div>\n    <div class="card"><div class="ico">⚡</div><h3>Status</h3><p>Health check and Swagger UI.</p>\n      <a class="btn" href="/health">Health</a></div>\n  </div>\n  <footer>Powered by <b>shawon</b></footer>\n</div>\n</body></html>'

COOKIE_HTML = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>\n<title>Cookies · shawon</title>\n<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700&family=Outfit:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet"/>\n<style>\n:root{--bg:#020617;--card:rgba(15,23,42,.8);--line:rgba(56,189,248,.16);--t:#f8fafc;--m:#94a3b8;--c:#22d3ee;--p:#a78bfa;--ok:#34d399;--err:#f87171}\n*{box-sizing:border-box;margin:0;padding:0}\nbody{font-family:Outfit,system-ui,sans-serif;background:var(--bg);color:var(--t);min-height:100vh}\nbody::before{content:"";position:fixed;inset:0;z-index:-1;background:radial-gradient(700px 400px at 10% -5%,rgba(34,211,238,.14),transparent 50%),var(--bg)}\n.wrap{max-width:540px;margin:0 auto;padding:0 14px 90px}\n.top{position:sticky;top:0;z-index:30;margin:0 -14px 18px;padding:12px 14px;display:flex;justify-content:space-between;align-items:center;background:rgba(2,6,23,.85);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}\n.brand{font-family:Orbitron,sans-serif;font-size:.78rem;color:var(--c);letter-spacing:.05em}\n.top a{color:var(--m);text-decoration:none;font-size:.8rem;margin-left:10px}\nheader{text-align:center;padding:10px 0 16px}\nh1{font-family:Orbitron,sans-serif;font-size:1.25rem;background:linear-gradient(120deg,#e0f2fe,var(--c),var(--p));-webkit-background-clip:text;-webkit-text-fill-color:transparent}\n.badge{display:inline-flex;margin-top:10px;padding:4px 11px;border-radius:999px;font-size:.76rem;font-weight:600}\n.badge.on{background:rgba(52,211,153,.12);color:var(--ok);border:1px solid rgba(52,211,153,.3)}\n.badge.off{background:rgba(248,113,113,.1);color:var(--err);border:1px solid rgba(248,113,113,.25)}\n.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;margin-bottom:12px}\n.card h2{font-size:.95rem;margin-bottom:8px}\n.easy{background:rgba(34,211,238,.06);border:1px solid rgba(34,211,238,.2);border-radius:12px;padding:12px;margin-bottom:10px;font-size:.85rem;color:var(--m)}\n.easy strong{display:block;color:var(--c);margin-bottom:4px}\n.easy ol{padding-left:18px}.easy li{margin:4px 0}\n.tabs{display:flex;gap:8px;margin-bottom:10px}\n.tab{flex:1;padding:10px;border-radius:11px;border:1px solid var(--line);background:transparent;color:var(--m);font-weight:600;cursor:pointer}\n.tab.active{background:linear-gradient(135deg,#0891b2,#7c3aed);color:#fff;border-color:transparent}\n.panel{display:none}.panel.active{display:block}\ntextarea,input[type=file]{width:100%;background:#020617;border:1px solid var(--line);border-radius:11px;color:var(--t);padding:11px;font-family:JetBrains Mono,monospace;font-size:.8rem;margin-bottom:8px}\ntextarea{min-height:110px}\n.btn{width:100%;padding:12px;border:0;border-radius:11px;font-weight:700;cursor:pointer;background:linear-gradient(135deg,var(--c),#67e8f9);color:#022}\n.btn-g{width:100%;margin-top:8px;padding:10px;border-radius:11px;background:transparent;border:1px solid var(--line);color:var(--m);cursor:pointer}\n.msg{margin-top:10px;padding:10px;border-radius:10px;font-size:.84rem;display:none}\n.msg.ok{display:block;background:rgba(52,211,153,.1);border:1px solid rgba(52,211,153,.3);color:var(--ok)}\n.msg.err{display:block;background:rgba(248,113,113,.08);border:1px solid rgba(248,113,113,.25);color:var(--err)}\nfooter{text-align:center;margin-top:24px;color:var(--m);font-size:.78rem}\nfooter b{color:var(--c);font-family:Orbitron,sans-serif}\n</style></head>\n<body>\n<div class="wrap">\n  <div class="top"><div class="brand">SHAWON · VAULT</div><div><a href="/">Home</a><a href="/docs">Docs</a></div></div>\n  <header><h1>Cookie Vault</h1><p style="color:var(--m);font-size:.88rem;margin-top:4px">Optional for restricted videos</p>\n    <div><span id="badge" class="badge off">● Loading…</span></div></header>\n  <div class="card">\n    <h2>Quick setup</h2>\n    <div class="easy"><strong>1) Extension</strong><ol>\n      <li>Install <b>Get cookies.txt LOCALLY</b></li>\n      <li>Login on youtube.com → Export</li>\n      <li>Upload below</li></ol></div>\n    <div class="easy"><strong>2) Paste header</strong><ol>\n      <li>Desktop: F12 → Network → Cookie header</li>\n      <li>Paste in Paste tab</li></ol></div>\n  </div>\n  <div class="card">\n    <div class="tabs">\n      <button type="button" class="tab active" data-tab="upload">Upload</button>\n      <button type="button" class="tab" data-tab="paste">Paste</button>\n    </div>\n    <div id="panel-upload" class="panel active">\n      <input type="file" id="file" accept=".txt,text/plain,*/*"/>\n      <button type="button" class="btn" id="btn-up">Save cookies</button>\n    </div>\n    <div id="panel-paste" class="panel">\n      <textarea id="txt" placeholder="Cookie header or cookies.txt contents"></textarea>\n      <button type="button" class="btn" id="btn-paste">Save cookies</button>\n    </div>\n    <button type="button" class="btn-g" id="btn-clear">Clear</button>\n    <div id="msg" class="msg"></div>\n  </div>\n  <footer>Locked to <b>shawon</b></footer>\n</div>\n<script>\n(function(){\n  var badge=document.getElementById("badge"),msg=document.getElementById("msg");\n  function show(ok,t){msg.className="msg "+(ok?"ok":"err");msg.textContent=t}\n  async function refresh(){try{var j=await(await fetch("/cookies/status")).json();var s=j.data||{};\n    if(s.has_cookies){badge.className="badge on";badge.textContent="● Active"}\n    else{badge.className="badge off";badge.textContent="● No cookies"}}catch(e){badge.textContent="● Offline"}}\n  refresh();\n  document.querySelectorAll(".tab").forEach(function(t){t.onclick=function(){\n    document.querySelectorAll(".tab").forEach(function(x){x.classList.remove("active")});\n    document.querySelectorAll(".panel").forEach(function(x){x.classList.remove("active")});\n    t.classList.add("active");document.getElementById("panel-"+t.dataset.tab).classList.add("active")}});\n  document.getElementById("btn-up").onclick=async function(){\n    var f=document.getElementById("file").files[0];if(!f)return show(false,"Choose file");\n    var fd=new FormData();fd.append("file",f);this.disabled=true;\n    try{var j=await(await fetch("/cookies/upload",{method:"POST",body:fd})).json();\n      if(j.ok){show(true,"Saved");refresh()}else show(false,j.error||"Failed")}catch(e){show(false,String(e))}\n    this.disabled=false};\n  document.getElementById("btn-paste").onclick=async function(){\n    var v=(document.getElementById("txt").value||"").trim();if(v.length<20)return show(false,"Too short");\n    var fd=new FormData();fd.append("cookie_string",v);this.disabled=true;\n    try{var j=await(await fetch("/cookies/paste",{method:"POST",body:fd})).json();\n      if(j.ok){show(true,"Saved");refresh()}else show(false,j.error||"Failed")}catch(e){show(false,String(e))}\n    this.disabled=false};\n  document.getElementById("btn-clear").onclick=async function(){\n    if(!confirm("Clear?"))return;\n    try{var j=await(await fetch("/cookies",{method:"DELETE"})).json();show(!!j.ok,j.ok?"Cleared":"Failed");refresh()}catch(e){show(false,String(e))}}\n})();\n</script>\n</body></html>'

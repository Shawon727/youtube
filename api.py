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

from cookie_manager import CookieManager

# ── identity lock ─────────────────────────────────────────
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

VERSION = "1.5.1"
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy services — avoid heavy import-time work on Vercel cold start
_cookies: Optional[CookieManager] = None
_yt = None
_ytm = None


def cookies() -> CookieManager:
    global _cookies
    if _cookies is None:
        _cookies = CookieManager()
    return _cookies


def yt():
    global _yt
    if _yt is None:
        from youtube_api import YouTubeAPI
        _yt = YouTubeAPI()
    return _yt


def ytm():
    global _ytm
    if _ytm is None:
        from ytm_api import YouTubeMusicAPI
        _ytm = YouTubeMusicAPI()
    return _ytm


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


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content=exc.detail if isinstance(exc.detail, dict) else fail(str(exc.detail)))
    return JSONResponse(status_code=500, content=fail(str(exc)[:300]))


@app.get("/docs", include_in_schema=False)
async def swagger_ui():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url or "/openapi.json",
        title="StreamHub API · shawon",
        swagger_ui_parameters={"docExpansion": "none", "defaultModelsExpandDepth": -1},
    )


@app.get("/", response_class=HTMLResponse)
async def home():
    if _DEAD:
        return HTMLResponse("<h1>API offline</h1>", status_code=503)
    return HOME_HTML


@app.get("/health")
async def health():
    _guard()
    return ok({"status": "alive", "ts": int(time.time()), "cookies": cookies().status(), "creator": CREATOR})


# ── YouTube ───────────────────────────────────────────────
@app.get("/yt/streams/{video_id}")
async def yt_streams(video_id: str):
    """Direct CDN video + audio streams."""
    _guard()
    try:
        data = await yt().get_streams(video_id)
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
        data = await yt().get_streams(video_id)
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/search")
async def yt_search(q: str = Query(..., min_length=1), filter: str = Query("all"), limit: int = Query(20, ge=1, le=50)):
    _guard()
    try:
        return ok(await yt().search(q, filter=filter, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/trending")
async def yt_trending(region: str = Query("US", min_length=2, max_length=2), category: str = Query("default")):
    _guard()
    try:
        return ok(await yt().trending(region=region.upper(), category=category))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/channel/{channel_id}")
async def yt_channel(channel_id: str, limit: int = Query(20, ge=1, le=50)):
    _guard()
    try:
        return ok(await yt().get_channel(channel_id, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/playlist/{playlist_id}")
async def yt_playlist(playlist_id: str, limit: int = Query(50, ge=1, le=100)):
    _guard()
    try:
        return ok(await yt().get_playlist(playlist_id, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/comments/{video_id}")
async def yt_comments(video_id: str, limit: int = Query(30, ge=1, le=100)):
    _guard()
    try:
        return ok(await yt().get_comments(video_id, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/suggestions")
async def yt_suggestions(q: str = Query(..., min_length=1)):
    _guard()
    try:
        return ok(await yt().suggestions(q))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/yt/info")
async def yt_info(url: str = Query(...)):
    _guard()
    try:
        return ok(await yt().extract_info(url))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


# ── YouTube Music ─────────────────────────────────────────
@app.get("/ytm/search")
async def ytm_search(q: str = Query(..., min_length=1), filter: str = Query("songs"), limit: int = Query(20, ge=1, le=50)):
    _guard()
    try:
        return ok(await ytm().search(q, filter=filter, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/home")
async def ytm_home(limit: int = Query(6, ge=1, le=12)):
    _guard()
    try:
        return ok(await ytm().home(limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/charts")
async def ytm_charts(country: str = Query("ZZ")):
    _guard()
    try:
        return ok(await ytm().charts(country=country.upper()))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/artist/{artist_id}")
async def ytm_artist(artist_id: str):
    _guard()
    try:
        return ok(await ytm().get_artist(artist_id))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/album/{browse_id}")
async def ytm_album(browse_id: str):
    _guard()
    try:
        return ok(await ytm().get_album(browse_id))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/playlist/{playlist_id}")
async def ytm_playlist(playlist_id: str, limit: int = Query(100, ge=1, le=200)):
    _guard()
    try:
        return ok(await ytm().get_playlist(playlist_id, limit=limit))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/play/{video_id}")
async def ytm_play(video_id: str):
    """Direct audio CDN URL."""
    _guard()
    try:
        data = await ytm().play(video_id)
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
        data = await ytm().play(video_id)
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
        return ok(await ytm().get_watch_playlist(video_id, playlist_id=playlist_id, radio=radio))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/lyrics/{video_id}")
async def ytm_lyrics(video_id: str):
    _guard()
    try:
        return ok(await ytm().get_lyrics(video_id))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/suggestions")
async def ytm_suggestions(q: str = Query(..., min_length=1)):
    _guard()
    try:
        return ok(await ytm().suggestions(q))
    except Exception as e:
        raise HTTPException(502, detail=fail(str(e)))


@app.get("/ytm/moods")
async def ytm_moods():
    _guard()
    try:
        return ok(await ytm().get_moods_and_genres())
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
    return ok(cookies().status())


@app.post("/cookies/upload")
async def cookie_upload(file: UploadFile = File(...)):
    _guard()
    try:
        text = (await file.read()).decode("utf-8", errors="ignore")
        path = cookies().save_netscape(text)
        try:
            yt().reload_cookies()
            ytm().reload_cookies()
        except Exception:
            pass
        return ok({"message": "Cookies saved", "path": str(path), "status": cookies().status()})
    except Exception as e:
        return JSONResponse(status_code=400, content=fail(str(e)))


@app.post("/cookies/paste")
async def cookie_paste(cookie_string: str = Form(...)):
    _guard()
    try:
        path = cookies().save_from_header(cookie_string)
        try:
            yt().reload_cookies()
            ytm().reload_cookies()
        except Exception:
            pass
        return ok({"message": "Cookies saved", "path": str(path), "status": cookies().status()})
    except Exception as e:
        return JSONResponse(status_code=400, content=fail(str(e)))


@app.delete("/cookies")
async def cookie_clear():
    _guard()
    cookies().clear()
    try:
        yt().reload_cookies()
        ytm().reload_cookies()
    except Exception:
        pass
    return ok({"message": "Cookies cleared"})


HOME_HTML = '<!DOCTYPE html>\n<html lang="en"><head>\n<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>\n<title>StreamHub · shawon</title>\n<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet"/>\n<style>\n:root{--bg:#020617;--card:rgba(15,23,42,.78);--line:rgba(56,189,248,.18);--t:#f8fafc;--m:#94a3b8;--c:#22d3ee;--p:#a78bfa}\n*{box-sizing:border-box;margin:0;padding:0}\nbody{font-family:Outfit,system-ui,sans-serif;background:var(--bg);color:var(--t);min-height:100vh}\nbody::before{content:"";position:fixed;inset:0;z-index:-1;background:radial-gradient(800px 480px at 10% -10%,rgba(34,211,238,.18),transparent 55%),radial-gradient(600px 400px at 95% 5%,rgba(167,139,250,.14),transparent 50%),var(--bg)}\n.wrap{max-width:960px;margin:0 auto;padding:0 16px 90px}\n.top{position:sticky;top:0;z-index:40;margin:0 -16px 22px;padding:12px 16px;display:flex;justify-content:space-between;align-items:center;background:rgba(2,6,23,.85);backdrop-filter:blur(14px);border-bottom:1px solid var(--line)}\n.brand{font-family:Orbitron,sans-serif;font-size:.84rem;letter-spacing:.06em;color:var(--c)}\n.top a{color:var(--m);text-decoration:none;font-size:.82rem;margin-left:10px}\n.top a:hover{color:var(--t)}\nheader{text-align:center;padding:26px 0 28px}\nh1{font-family:Orbitron,sans-serif;font-size:clamp(1.5rem,5vw,2.3rem);background:linear-gradient(120deg,#e0f2fe,var(--c),var(--p));-webkit-background-clip:text;-webkit-text-fill-color:transparent}\nheader p{color:var(--m);margin-top:10px}\n.chip{display:inline-block;margin-top:12px;padding:5px 12px;border-radius:999px;font-size:.74rem;border:1px solid var(--line);color:var(--c)}\n.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}\n.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px}\n.card h3{margin-bottom:6px}\n.card p{color:var(--m);font-size:.88rem;margin-bottom:10px}\ncode{font-size:.74rem;color:#7dd3fc}\n.btn{display:inline-block;margin-top:8px;padding:9px 14px;border-radius:999px;background:linear-gradient(135deg,var(--c),#67e8f9);color:#022;text-decoration:none;font-weight:700;font-size:.84rem}\nfooter{text-align:center;margin-top:36px;color:var(--m);font-size:.82rem;border-top:1px solid var(--line);padding-top:16px}\nfooter b{color:var(--c);font-family:Orbitron,sans-serif}\n</style></head><body>\n<div class="wrap">\n<div class="top"><div class="brand">STREAMHUB</div><div><a href="/docs">Docs</a><a href="/cookies">Cookies</a><a href="/health">Health</a></div></div>\n<header><h1>YouTube + Music API</h1><p>Direct CDN · download · search</p><div class="chip">creator · shawon · v1.5.1</div></header>\n<div class="grid">\n<div class="card"><h3>📺 YouTube</h3><p>Streams & download</p><div><code>/yt/streams/{id}</code></div><div><code>/yt/download/{id}</code></div><a class="btn" href="/docs">Docs</a></div>\n<div class="card"><h3>🎵 Music</h3><p>Play & audio download</p><div><code>/ytm/play/{id}</code></div><div><code>/ytm/download/{id}</code></div><a class="btn" href="/docs">Docs</a></div>\n<div class="card"><h3>🍪 Cookies</h3><p>Optional restricted unlock</p><a class="btn" href="/cookies">Vault</a></div>\n<div class="card"><h3>⚡ Status</h3><p>Health check</p><a class="btn" href="/health">Health</a></div>\n</div>\n<footer>Powered by <b>shawon</b></footer>\n</div></body></html>'
COOKIE_HTML = '<!DOCTYPE html>\n<html lang="en"><head>\n<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>\n<title>Cookies · shawon</title>\n<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@600&family=Outfit:wght@400;500;600&display=swap" rel="stylesheet"/>\n<style>\n:root{--bg:#020617;--card:rgba(15,23,42,.85);--line:rgba(56,189,248,.16);--t:#f8fafc;--m:#94a3b8;--c:#22d3ee;--ok:#34d399;--err:#f87171}\n*{box-sizing:border-box;margin:0;padding:0}\nbody{font-family:Outfit,system-ui,sans-serif;background:var(--bg);color:var(--t);min-height:100vh}\n.wrap{max-width:520px;margin:0 auto;padding:0 14px 80px}\n.top{position:sticky;top:0;padding:12px 0;display:flex;justify-content:space-between;background:rgba(2,6,23,.9);border-bottom:1px solid var(--line);margin-bottom:16px}\n.brand{font-family:Orbitron,sans-serif;font-size:.78rem;color:var(--c)}\n.top a{color:var(--m);text-decoration:none;font-size:.8rem;margin-left:10px}\nheader{text-align:center;margin-bottom:14px}\nh1{font-family:Orbitron,sans-serif;font-size:1.2rem;color:var(--c)}\n.badge{display:inline-block;margin-top:8px;padding:4px 10px;border-radius:999px;font-size:.75rem}\n.badge.on{color:var(--ok);border:1px solid rgba(52,211,153,.3)}\n.badge.off{color:var(--err);border:1px solid rgba(248,113,113,.25)}\n.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;margin-bottom:12px}\n.tabs{display:flex;gap:8px;margin-bottom:10px}\n.tab{flex:1;padding:10px;border-radius:10px;border:1px solid var(--line);background:transparent;color:var(--m);cursor:pointer}\n.tab.active{background:linear-gradient(135deg,#0891b2,#7c3aed);color:#fff;border:0}\n.panel{display:none}.panel.active{display:block}\ntextarea,input[type=file]{width:100%;background:#020617;border:1px solid var(--line);border-radius:10px;color:var(--t);padding:10px;margin-bottom:8px}\ntextarea{min-height:100px}\n.btn{width:100%;padding:12px;border:0;border-radius:10px;font-weight:700;cursor:pointer;background:linear-gradient(135deg,var(--c),#67e8f9);color:#022}\n.btn-g{width:100%;margin-top:8px;padding:10px;border-radius:10px;background:transparent;border:1px solid var(--line);color:var(--m);cursor:pointer}\n.msg{margin-top:10px;padding:10px;border-radius:8px;font-size:.84rem;display:none}\n.msg.ok{display:block;color:var(--ok);border:1px solid rgba(52,211,153,.3)}\n.msg.err{display:block;color:var(--err);border:1px solid rgba(248,113,113,.25)}\n.easy{font-size:.84rem;color:var(--m);margin-bottom:8px}\nfooter{text-align:center;margin-top:20px;color:var(--m);font-size:.78rem}\nfooter b{color:var(--c)}\n</style></head><body>\n<div class="wrap">\n<div class="top"><div class="brand">SHAWON · VAULT</div><div><a href="/">Home</a><a href="/docs">Docs</a></div></div>\n<header><h1>Cookie Vault</h1><span id="badge" class="badge off">● Loading…</span></header>\n<div class="card"><div class="easy"><b style="color:var(--c)">Quick:</b> Export cookies.txt from youtube.com (extension) → Upload</div>\n<div class="tabs"><button type="button" class="tab active" data-tab="upload">Upload</button><button type="button" class="tab" data-tab="paste">Paste</button></div>\n<div id="panel-upload" class="panel active"><input type="file" id="file"/><button type="button" class="btn" id="btn-up">Save</button></div>\n<div id="panel-paste" class="panel"><textarea id="txt" placeholder="Cookie header or cookies.txt"></textarea><button type="button" class="btn" id="btn-paste">Save</button></div>\n<button type="button" class="btn-g" id="btn-clear">Clear</button><div id="msg" class="msg"></div></div>\n<footer>Locked to <b>shawon</b></footer></div>\n<script>\n(function(){var b=document.getElementById("badge"),m=document.getElementById("msg");\nfunction show(ok,t){m.className="msg "+(ok?"ok":"err");m.textContent=t}\nasync function refresh(){try{var j=await(await fetch("/cookies/status")).json();var s=j.data||{};\nb.className="badge "+(s.has_cookies?"on":"off");b.textContent=s.has_cookies?"● Active":"● No cookies"}catch(e){b.textContent="● Offline"}}\nrefresh();\ndocument.querySelectorAll(".tab").forEach(function(t){t.onclick=function(){\ndocument.querySelectorAll(".tab").forEach(function(x){x.classList.remove("active")});\ndocument.querySelectorAll(".panel").forEach(function(x){x.classList.remove("active")});\nt.classList.add("active");document.getElementById("panel-"+t.dataset.tab).classList.add("active")}});\ndocument.getElementById("btn-up").onclick=async function(){var f=document.getElementById("file").files[0];if(!f)return show(false,"Choose file");\nvar fd=new FormData();fd.append("file",f);try{var j=await(await fetch("/cookies/upload",{method:"POST",body:fd})).json();\nshow(!!j.ok,j.ok?"Saved":(j.error||"Failed"));refresh()}catch(e){show(false,String(e))}};\ndocument.getElementById("btn-paste").onclick=async function(){var v=(document.getElementById("txt").value||"").trim();if(v.length<20)return show(false,"Too short");\nvar fd=new FormData();fd.append("cookie_string",v);try{var j=await(await fetch("/cookies/paste",{method:"POST",body:fd})).json();\nshow(!!j.ok,j.ok?"Saved":(j.error||"Failed"));refresh()}catch(e){show(false,String(e))}};\ndocument.getElementById("btn-clear").onclick=async function(){if(!confirm("Clear?"))return;\ntry{var j=await(await fetch("/cookies",{method:"DELETE"})).json();show(!!j.ok,j.ok?"Cleared":"Failed");refresh()}catch(e){show(false,String(e))}}\n})();\n</script></body></html>'

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
from fastapi.responses import HTMLResponse

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
        raise HTTPException(400, detail=fail(str(e)))


@app.post("/cookies/paste")
async def cookie_paste(cookie_string: str = Form(...)):
    try:
        path = cookies.save_from_header(cookie_string)
        yt.reload_cookies()
        ytm.reload_cookies()
        return ok({"message": "Cookies saved from header", "path": str(path), "status": cookies.status()})
    except Exception as e:
        raise HTTPException(400, detail=fail(str(e)))


@app.delete("/cookies")
async def cookie_clear():
    cookies.clear()
    yt.reload_cookies()
    ytm.reload_cookies()
    return ok({"message": "Cookies cleared"})


HOME_HTML = '<!DOCTYPE html>\n<html lang="bn">\n<head>\n<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>\n<title>YT Stream API</title>\n<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+Bengali:wght@400;600&display=swap" rel="stylesheet"/>\n<style>\n:root{--bg:#070b14;--card:#0f1623;--border:#1e293b;--a:#3b82f6;--a2:#8b5cf6;--t:#e2e8f0;--m:#94a3b8}\n*{box-sizing:border-box;margin:0;padding:0}\nbody{font-family:Inter,\'Noto Sans Bengali\',system-ui,sans-serif;background:radial-gradient(1000px 600px at 20% -15%,#1e3a5f55,transparent),radial-gradient(800px 500px at 85% 10%,#4c1d9555,transparent),var(--bg);color:var(--t);min-height:100vh}\n.wrap{max-width:900px;margin:0 auto;padding:40px 20px 80px}\nheader{text-align:center;margin-bottom:40px}\nheader h1{font-size:2.2rem;font-weight:700;background:linear-gradient(135deg,#60a5fa,#c084fc,#f472b6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}\nheader p{color:var(--m);margin-top:10px;font-size:1rem}\n.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin-bottom:28px}\n.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:22px;transition:.2s}\n.card:hover{border-color:#3b82f680;transform:translateY(-2px)}\n.card h3{font-size:1.1rem;margin-bottom:8px}\n.card p{color:var(--m);font-size:.88rem;margin-bottom:14px}\n.card a{display:inline-block;padding:8px 14px;border-radius:999px;background:linear-gradient(135deg,var(--a),var(--a2));color:#fff;text-decoration:none;font-size:.85rem;font-weight:600}\ncode{background:#1e293b;padding:2px 7px;border-radius:5px;font-size:.8rem;color:#93c5fd}\n.ep{margin:6px 0;font-size:.84rem;color:var(--m)}\nfooter{text-align:center;color:var(--m);font-size:.85rem;margin-top:40px}\n.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:.75rem;font-weight:600;background:#1e3a5f;color:#93c5fd;margin-left:6px}\n</style>\n</head>\n<body>\n<div class="wrap">\n<header>\n  <h1>YT Stream API</h1>\n  <p>YouTube + YouTube Music · yt-dlp · ytmusicapi · Direct googlevideo CDN</p>\n</header>\n<div class="grid">\n  <div class="card">\n    <h3>📺 YouTube <span class="badge">/yt</span></h3>\n    <p>LibreTube / Piped style streams, search, trending, channel, playlist</p>\n    <div class="ep"><code>/yt/streams/{id}</code> → direct_video + direct_audio</div>\n    <div class="ep"><code>/yt/search?q=</code></div>\n    <div class="ep"><code>/yt/trending?region=US</code></div>\n    <a href="/docs#/default/yt_streams_yt_streams__video_id__get">Try in Docs →</a>\n  </div>\n  <div class="card">\n    <h3>🎵 YouTube Music <span class="badge">/ytm</span></h3>\n    <p>SimpMusic style home, charts, artist, album + direct audio CDN</p>\n    <div class="ep"><code>/ytm/play/{id}</code> → audio_url (CDN)</div>\n    <div class="ep"><code>/ytm/search?q=&filter=songs</code></div>\n    <div class="ep"><code>/ytm/home</code> · <code>/ytm/charts</code></div>\n    <a href="/docs">Try in Docs →</a>\n  </div>\n  <div class="card">\n    <h3>🍪 Cookies</h3>\n    <p>Bookmarklet দিয়ে এক ক্লিকে cookie বের করুন, অথবা cookies.txt আপলোড</p>\n    <a href="/cookies">Open Cookie Manager →</a>\n  </div>\n  <div class="card">\n    <h3>📖 Docs & Health</h3>\n    <p>Interactive Swagger + health check</p>\n    <a href="/docs" style="margin-right:8px">Swagger</a>\n    <a href="/health" style="background:#1e293b;border:1px solid #334155">Health</a>\n  </div>\n</div>\n<footer>creator: yt-stream · version 1.1.0</footer>\n</div>\n</body></html>'
COOKIE_HTML = '<!DOCTYPE html>\n<html lang="bn">\n<head>\n<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>\n<title>YT Stream — Cookie Manager</title>\n<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+Bengali:wght@400;500;600;700&display=swap" rel="stylesheet"/>\n<style>\n:root{--bg:#070b14;--card:#0f1623;--border:#1e293b;--a:#3b82f6;--a2:#8b5cf6;--t:#e2e8f0;--m:#94a3b8;--ok:#22c55e;--err:#ef4444;--r:16px}\n*{box-sizing:border-box;margin:0;padding:0}\nbody{font-family:Inter,\'Noto Sans Bengali\',system-ui,sans-serif;background:radial-gradient(900px 500px at 15% -10%,#1e3a5f44,transparent),radial-gradient(700px 400px at 90% 0%,#4c1d9544,transparent),var(--bg);color:var(--t);min-height:100vh;line-height:1.55}\n.wrap{max-width:760px;margin:0 auto;padding:28px 18px 90px}\nheader{text-align:center;margin-bottom:28px}\nheader h1{font-size:1.75rem;font-weight:700;background:linear-gradient(135deg,#60a5fa,#c084fc);-webkit-background-clip:text;-webkit-text-fill-color:transparent}\nheader p{color:var(--m);margin-top:8px;font-size:.93rem}\n.card{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:22px;margin-bottom:16px;box-shadow:0 10px 40px #0005}\n.card h2{font-size:1.1rem;margin-bottom:12px;display:flex;align-items:center;gap:8px}\n.steps{list-style:none;counter-reset:s}\n.steps li{counter-increment:s;position:relative;padding:11px 0 11px 42px;border-bottom:1px solid var(--border);color:var(--m);font-size:.9rem}\n.steps li:last-child{border-bottom:none}\n.steps li::before{content:counter(s);position:absolute;left:0;top:11px;width:28px;height:28px;background:linear-gradient(135deg,var(--a),var(--a2));color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.78rem;font-weight:700}\n.steps strong{color:var(--t)}\n.tabs{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}\n.tab{flex:1;min-width:120px;padding:10px;border:1px solid var(--border);background:transparent;color:var(--m);border-radius:10px;cursor:pointer;font-weight:500;font-size:.88rem;transition:.2s}\n.tab.active{background:linear-gradient(135deg,#1d4ed8,#6d28d9);color:#fff;border-color:transparent}\n.panel{display:none}.panel.active{display:block}\ntextarea,input[type=file]{width:100%;background:#0a101c;border:1px solid var(--border);border-radius:10px;color:var(--t);padding:12px;font-family:ui-monospace,monospace;font-size:.84rem;margin-bottom:10px}\ntextarea{min-height:110px;resize:vertical}\nbutton.primary{width:100%;padding:12px;background:linear-gradient(135deg,var(--a),var(--a2));border:none;border-radius:10px;color:#fff;font-weight:600;font-size:.94rem;cursor:pointer;transition:.15s}\nbutton.primary:hover{transform:translateY(-1px);opacity:.95}\nbutton.primary:disabled{opacity:.45;cursor:not-allowed;transform:none}\n.btn-row{display:flex;gap:10px;margin-top:8px}\n.btn-row button{flex:1}\nbutton.ghost{background:transparent;border:1px solid var(--border);color:var(--t);border-radius:10px;padding:10px;cursor:pointer;font-weight:500}\n.status{margin-top:14px;padding:12px 14px;border-radius:10px;font-size:.88rem;display:none}\n.status.ok{display:block;background:#14532d44;border:1px solid #22c55e55;color:#86efac}\n.status.err{display:block;background:#450a0a44;border:1px solid #ef444455;color:#fca5a5}\n.badge{display:inline-flex;align-items:center;gap:6px;padding:4px 12px;border-radius:999px;font-size:.8rem;font-weight:600}\n.badge.on{background:#14532d;color:#86efac}.badge.off{background:#3f1f1f;color:#fca5a5}\n.note{background:#1e293b55;border-left:3px solid var(--a2);padding:12px 14px;border-radius:0 10px 10px 0;font-size:.84rem;color:var(--m);margin-top:14px}\n.bookmarklet{display:inline-block;margin-top:10px;padding:10px 16px;background:linear-gradient(135deg,#0ea5e9,#6366f1);color:#fff;border-radius:10px;font-weight:600;text-decoration:none;font-size:.9rem}\ncode{background:#1e293b;padding:2px 6px;border-radius:4px;font-size:.82rem}\na{color:#60a5fa;text-decoration:none}a:hover{text-decoration:underline}\nfooter{text-align:center;margin-top:36px;color:var(--m);font-size:.84rem}\n.nav{display:flex;gap:10px;justify-content:center;margin-bottom:20px;flex-wrap:wrap}\n.nav a{padding:8px 14px;border-radius:999px;border:1px solid var(--border);color:var(--m);font-size:.85rem}\n.nav a:hover{border-color:var(--a);color:var(--t)}\n</style>\n</head>\n<body>\n<div class="wrap">\n<header>\n  <h1>🍪 Cookie Manager</h1>\n  <p>YouTube / YouTube Music cookies — age-restricted, Premium quality, private content</p>\n  <div style="margin-top:12px"><span id="badge" class="badge off">● Loading…</span></div>\n</header>\n<div class="nav">\n  <a href="/">🏠 Home</a>\n  <a href="/docs">📖 API Docs</a>\n  <a href="/cookies/status">⚡ Status JSON</a>\n</div>\n\n<div class="card">\n  <h2><span>⚡</span> এক ক্লিকে Cookie বের করুন (Bookmarklet)</h2>\n  <p style="color:var(--m);font-size:.9rem;margin-bottom:8px">\n    নিচের বাটনটিকে বুকমার্ক বারে টেনে নিন। তারপর <strong>youtube.com</strong> বা <strong>music.youtube.com</strong> এ লগইন অবস্থায় বুকমার্কে ক্লিক করুন — Cookie অটো কপি হবে।\n  </p>\n  <a class="bookmarklet" id="bm" href="#">🍪 Get YT Cookies</a>\n  <div class="note">মোবাইলে: লিংক কপি করে নতুন বুকমার্ক বানিয়ে URL ফিল্ডে পেস্ট করুন।</div>\n</div>\n\n<div class="card">\n  <h2><span>📖</span> ম্যানুয়াল উপায়</h2>\n  <ol class="steps">\n    <li><strong>Chrome / Edge / Brave</strong> এ <a href="https://music.youtube.com" target="_blank">music.youtube.com</a> লগইন করুন।</li>\n    <li><strong>Get cookies.txt LOCALLY</strong> এক্সটেনশন ইন্সটল → Export → <code>cookies.txt</code> সেভ।</li>\n    <li>অথবা F12 → Network → যেকোনো request → Headers → <code>Cookie:</code> পুরো ভ্যালু কপি।</li>\n    <li>নিচে আপলোড বা পেস্ট করুন।</li>\n  </ol>\n</div>\n\n<div class="card">\n  <div class="tabs">\n    <button class="tab active" data-tab="upload">📁 Upload cookies.txt</button>\n    <button class="tab" data-tab="paste">📋 Paste Cookie string</button>\n  </div>\n  <div id="panel-upload" class="panel active">\n    <input type="file" id="file" accept=".txt,text/plain"/>\n    <button class="primary" id="btn-upload">Upload &amp; Save</button>\n  </div>\n  <div id="panel-paste" class="panel">\n    <textarea id="cookie-str" placeholder="SID=...; HSID=...; SSID=...; APISID=...; SAPISID=...;"></textarea>\n    <button class="primary" id="btn-paste">Save Cookie String</button>\n  </div>\n  <div class="btn-row"><button class="ghost" id="btn-clear">🗑 Clear Cookies</button></div>\n  <div id="msg" class="status"></div>\n</div>\n\n<div class="card">\n  <h2><span>🔗</span> Quick test</h2>\n  <p style="color:var(--m);font-size:.88rem">\n    <code>GET /yt/streams/dQw4w9WgXcQ</code> · <code>GET /ytm/play/dQw4w9WgXcQ</code><br/>\n    Response এ <code>direct_video</code> / <code>direct_audio</code> / <code>audio_url</code> = googlevideo CDN\n  </p>\n</div>\n<footer>YT Stream API · yt-dlp + ytmusicapi</footer>\n</div>\n<script>\nconst badge=document.getElementById(\'badge\'),msg=document.getElementById(\'msg\');\nconst bmCode="javascript:(function(){try{var c=document.cookie;if(!c||c.length<10){alert(\'No cookies found. Login to YouTube first.\');return;}navigator.clipboard.writeText(c).then(function(){alert(\'✅ YouTube cookies copied!\\\\nPaste in YT Stream Cookie Manager.\');}).catch(function(){prompt(\'Copy cookies:\',c);});}catch(e){alert(e);}})();";\ndocument.getElementById(\'bm\').href=bmCode;\nasync function refresh(){try{const r=await fetch(\'/cookies/status\');const j=await r.json();const s=j.data||{};if(s.has_cookies){badge.className=\'badge on\';badge.textContent=\'● Cookies active\'+(s.mtime?\' · \'+s.mtime:\'\');}else{badge.className=\'badge off\';badge.textContent=\'● No cookies\';}}catch{badge.className=\'badge off\';badge.textContent=\'● Status unavailable\';}}\nrefresh();\ndocument.querySelectorAll(\'.tab\').forEach(t=>t.addEventListener(\'click\',()=>{document.querySelectorAll(\'.tab\').forEach(x=>x.classList.remove(\'active\'));document.querySelectorAll(\'.panel\').forEach(x=>x.classList.remove(\'active\'));t.classList.add(\'active\');document.getElementById(\'panel-\'+t.dataset.tab).classList.add(\'active\');}));\nfunction show(ok,t){msg.className=\'status \'+(ok?\'ok\':\'err\');msg.textContent=t;}\ndocument.getElementById(\'btn-upload\').onclick=async()=>{const f=document.getElementById(\'file\').files[0];if(!f)return show(false,\'cookies.txt সিলেক্ট করুন\');const fd=new FormData();fd.append(\'file\',f);const b=document.getElementById(\'btn-upload\');b.disabled=true;try{const r=await fetch(\'/cookies/upload\',{method:\'POST\',body:fd});const j=await r.json();if(j.ok){show(true,\'✅ Cookies saved\');refresh();}else show(false,j.error||\'Failed\');}catch(e){show(false,String(e));}finally{b.disabled=false;}};\ndocument.getElementById(\'btn-paste\').onclick=async()=>{const v=document.getElementById(\'cookie-str\').value.trim();if(v.length<20)return show(false,\'Cookie string খুব ছোট\');const fd=new FormData();fd.append(\'cookie_string\',v);const b=document.getElementById(\'btn-paste\');b.disabled=true;try{const r=await fetch(\'/cookies/paste\',{method:\'POST\',body:fd});const j=await r.json();if(j.ok){show(true,\'✅ Saved from header\');refresh();}else show(false,j.error||\'Failed\');}catch(e){show(false,String(e));}finally{b.disabled=false;}};\ndocument.getElementById(\'btn-clear\').onclick=async()=>{if(!confirm(\'Clear all cookies?\'))return;try{const r=await fetch(\'/cookies\',{method:\'DELETE\'});const j=await r.json();show(!!j.ok,j.ok?\'Cleared\':\'Failed\');refresh();}catch(e){show(false,String(e));}};\n</script>\n</body></html>'

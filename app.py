"""YouTube -> audio direto (resolvedor p/ SA-MP).
Uso: GET /resolve?url=<youtube-url>
Retorna HTTP 302 para o stream de audio direto (melhor formato audio-only).
O SA-MP (PlayAudioStreamForPlayer) segue o redirect e toca o audio.
"""
import os
import re
from flask import Flask, request, redirect, jsonify
import yt_dlp

app = Flask(__name__)

YT_RE = re.compile(r"(youtube\.com/watch|youtu\.be/|youtube\.com/shorts/)", re.I)

# Cookies do YouTube (opcional): o conteudo vem pela variavel de ambiente
# YT_COOKIES no Render (nunca vai para o GitHub publico). Se estiver definida,
# grava num arquivo local e passa ao yt-dlp, para o YouTube nao pedir login
# em IP de servidor. O arquivo tambem pode existir localmente (cookies.txt)
# para teste fora do Render.
_COOKIE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
_env_cookies = os.environ.get("YT_COOKIES", "")
if _env_cookies.strip():
    try:
        # Aceita tanto quebras de linha reais quanto "\n" literal
        _content = _env_cookies.replace("\\n", "\n")
        with open(_COOKIE_PATH, "w", encoding="utf-8") as _f:
            _f.write(_content)
    except Exception:
        pass

YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    # Prefere m4a (AAC, itag 140) — mais compativel com o BASS do SA-MP
    # do que Opus/WebM (itag 251). Cai para bestaudio se nao houver m4a.
    "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio",
    "extract_flat": False,
    "skip_download": True,
}
if os.path.exists(_COOKIE_PATH) and os.path.getsize(_COOKIE_PATH) > 0:
    YDL_OPTS["cookiefile"] = _COOKIE_PATH


def extract_audio_url(yt_url):
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(yt_url, download=False)
        # Se for playlist/resultado multiplo, pega a primeira entrada
        if info.get("entries"):
            info = info["entries"][0]
        # Melhor formato de audio
        url = info.get("url")
        if url:
            return url, info.get("title", ""), info.get("duration", 0)
        # Fallback: procura nos formatos o melhor audio-only
        fmts = info.get("formats") or []
        audio_only = [f for f in fmts if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none")]
        if audio_only:
            best = max(audio_only, key=lambda f: f.get("abr") or 0)
            return best["url"], info.get("title", ""), info.get("duration", 0)
        return None, info.get("title", ""), info.get("duration", 0)


@app.route("/")
def index():
    return jsonify({
        "ok": True,
        "service": "yt-resolver",
        "usage": "/resolve?url=<youtube-url>",
        "cookies": bool(YDL_OPTS.get("cookiefile")),
    })


@app.route("/search")
def search():
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"ok": False, "error": "missing q param"}), 400
    if len(query) > 200:
        return jsonify({"ok": False, "error": "query too long"}), 400
    try:
        # ytsearch1: pega o primeiro resultado da busca no YouTube
        audio_url, title, duration = extract_audio_url("ytsearch1:" + query)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:300]}), 502
    if not audio_url:
        return jsonify({"ok": False, "error": "no result found"}), 502
    resp = redirect(audio_url, code=302)
    resp.headers["X-Title"] = title[:200]
    resp.headers["X-Duration"] = str(duration)
    return resp


@app.route("/resolve")
def resolve():
    yt_url = (request.args.get("url") or "").strip()
    if not yt_url:
        return jsonify({"ok": False, "error": "missing url param"}), 400
    if not YT_RE.search(yt_url):
        return jsonify({"ok": False, "error": "not a youtube url"}), 400
    try:
        audio_url, title, duration = extract_audio_url(yt_url)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:300]}), 502
    if not audio_url:
        return jsonify({"ok": False, "error": "no audio stream found"}), 502
    resp = redirect(audio_url, code=302)
    resp.headers["X-Title"] = title[:200]
    resp.headers["X-Duration"] = str(duration)
    return resp


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

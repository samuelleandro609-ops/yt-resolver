"""YouTube -> audio direto (resolvedor p/ SA-MP).
Uso: GET /resolve?url=<youtube-url>
Retorna HTTP 302 para o stream de audio direto (melhor formato audio-only).
O SA-MP (PlayAudioStreamForPlayer) segue o redirect e toca o audio.
"""
import re
from flask import Flask, request, redirect, jsonify
import yt_dlp

app = Flask(__name__)

YT_RE = re.compile(r"(youtube\.com/watch|youtu\.be/|youtube\.com/shorts/)", re.I)

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
    return jsonify({"ok": True, "service": "yt-resolver", "usage": "/resolve?url=<youtube-url>"})


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

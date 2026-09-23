import os
import uvicorn
import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

app = FastAPI(title="AuraStream Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def serve_frontend():
    if os.path.exists("music.html"):
        return FileResponse("music.html")
    return {"error": "music.html not found"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "AuraStream Backend"}

@app.get("/api/search")
async def search_tracks(q: str = Query(..., description="Search query")):
    ydl_opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "default_search": "ytsearch10",
        "extract_flat": "in_playlist",
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch10:{q}", download=False)
            tracks = []
            if "entries" in info:
                for entry in info["entries"]:
                    if entry:
                        tracks.append({
                            "id": entry.get("id"),
                            "title": entry.get("title"),
                            "artist": entry.get("uploader") or entry.get("channel") or "AuraStream Artist",
                            "thumbnail": entry.get("thumbnail") or f"https://i.ytimg.com/vi/{entry.get('id')}/hqdefault.jpg"
                        })
            return tracks
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# AUDIO PROXY: Pipes audio chunks directly so browsers bypass YouTube 403 / CORS bans
@app.get("/api/stream/{video_id}")
async def stream_audio_proxy(video_id: str, request: Request):
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "quiet": True,
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            stream_url = info.get("url")
            if not stream_url:
                raise HTTPException(status_code=404, detail="Audio stream not found")

        # Forward range headers for seamless mobile scrubbing
        req_headers = {"User-Agent": "Mozilla/5.0"}
        range_header = request.headers.get("range")
        if range_header:
            req_headers["Range"] = range_header

        client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        upstream_req = client.build_request("GET", stream_url, headers=req_headers)
        upstream_res = await client.send(upstream_req, stream=True)

        async def audio_chunk_generator():
            try:
                async for chunk in upstream_res.aiter_bytes(chunk_size=65536):
                    yield chunk
            finally:
                await upstream_res.aclose()
                await client.aclose()

        response_headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": upstream_res.headers.get("content-type", "audio/mp4"),
        }
        if "content-length" in upstream_res.headers:
            response_headers["Content-Length"] = upstream_res.headers["content-length"]
        if "content-range" in upstream_res.headers:
            response_headers["Content-Range"] = upstream_res.headers["content-range"]

        return StreamingResponse(
            audio_chunk_generator(),
            status_code=upstream_res.status_code,
            headers=response_headers,
            media_type="audio/mp4"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("server:app", host="0.0.0.0", port=port)

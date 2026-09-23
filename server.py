import os
import uvicorn
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

app = FastAPI(title="AuraStream Backend")

# Enable Cross-Origin Resource Sharing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Serve the Visual Frontend Interface
@app.get("/")
async def serve_frontend():
    if os.path.exists("music.html"):
        return FileResponse("music.html")
    return {"error": "music.html not found. Ensure it is uploaded to the root directory."}

# Health Check Route
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "AuraStream Backend"}

# 2. Search Endpoint for YouTube Tracks
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

# 3. Stream Proxy Endpoint
@app.get("/api/stream/{video_id}")
async def get_stream_url(video_id: str):
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
                raise HTTPException(status_code=404, detail="Direct audio stream not found")
            return {"streamUrl": stream_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 4. Dynamic Port Launcher (Render Cloud & Local Support)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("server:app", host="0.0.0.0", port=port)

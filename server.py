import os
import uvicorn
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from yt_dlp import YoutubeDL

app = FastAPI(title="AuraStream Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

YTDL_SEARCH_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "extract_flat": True,
    "skip_download": True,
}

YTDL_STREAM_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "ios", "web_safari"]
        }
    }
}

@app.get("/")
def read_root():
    return {"status": "ok", "service": "AuraStream Backend"}

@app.get("/api/search")
def search_tracks(q: str):
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")
    
    try:
        with YoutubeDL(YTDL_SEARCH_OPTS) as ydl:
            result = ydl.extract_info(f"ytsearch15:{q}", download=False)
            entries = result.get("entries", [])
            
            tracks = []
            for item in entries:
                if not item:
                    continue
                tracks.append({
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "artist": item.get("uploader", "Unknown Artist"),
                    "duration": item.get("duration", 0),
                    "poster": f"https://i.ytimg.com/vi/{item.get('id')}/hqdefault.jpg"
                })
            return {"tracks": tracks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stream/{video_id}")
def get_stream(video_id: str, request: Request):
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        with YoutubeDL(YTDL_STREAM_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Point the frontend to our own proxy streaming endpoint
            base_host = str(request.base_url).rstrip("/")
            proxy_url = f"{base_host}/api/proxy-audio/{video_id}"
            
            return {
                "id": video_id,
                "streamUrl": proxy_url,
                "title": info.get("title"),
                "artist": info.get("uploader", "AuraStream Artist")
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/proxy-audio/{video_id}")
async def proxy_audio(video_id: str):
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        with YoutubeDL(YTDL_STREAM_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            stream_url = info.get("url")
        
        client = httpx.AsyncClient()
        req = client.build_request("GET", stream_url)
        r = await client.send(req, stream=True)

        async def stream_generator():
            try:
                async for chunk in r.aiter_raw():
                    yield chunk
            finally:
                await r.aclose()
                await client.aclose()

        return StreamingResponse(
            stream_generator(),
            media_type="audio/mp4",
            headers={"Accept-Ranges": "bytes"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)

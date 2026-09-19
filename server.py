import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from yt_dlp import YoutubeDL

app = FastAPI(title="AuraStream Backend")

# Enable CORS so your local or hosted music.html can make requests without restrictions
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
}


@app.get("/")
def health_check():
    return {"status": "ok", "service": "AuraStream Backend"}


@app.get("/api/search")
def search_tracks(q: str):
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")

    query = f"ytsearch15:{q.strip()}"
    try:
        with YoutubeDL(YTDL_SEARCH_OPTS) as ydl:
            res = ydl.extract_info(query, download=False)
            entries = res.get("entries", [])

            results = []
            for item in entries:
                if not item:
                    continue

                # Safely parse thumbnail URL
                thumb = item.get("thumbnail")
                if not thumb and item.get("thumbnails"):
                    thumb = item["thumbnails"][0].get("url")
                if not thumb:
                    thumb = f"https://img.youtube.com/vi/{item.get('id')}/hqdefault.jpg"

                results.append({
                    "id": item.get("id"),
                    "title": item.get("title", "Unknown Track"),
                    "uploader": item.get("uploader") or item.get("channel") or "Unknown Artist",
                    "thumbnail": thumb,
                    "duration": item.get("duration", 0),
                })
            return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/api/stream/{video_id}")
def get_stream(video_id: str):
    if not video_id:
        raise HTTPException(status_code=400, detail="Missing video ID.")

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with YoutubeDL(YTDL_STREAM_OPTS) as ydl:
            info = ydl.extract_info(video_url, download=False)
            stream_url = info.get("url")

            # Fallback format selection if default url isn't top-level
            if not stream_url and "formats" in info:
                audio_formats = [f for f in info["formats"] if f.get("acodec") != "none"]
                if audio_formats:
                    stream_url = audio_formats[-1].get("url")

            if not stream_url:
                raise HTTPException(status_code=404, detail="Direct stream URL could not be extracted.")

            return {
                "id": video_id,
                "streamUrl": stream_url,
                "title": info.get("title"),
                "artist": info.get("uploader"),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stream resolution error: {str(e)}")


if __name__ == "__main__":
    # Dynamically reads the PORT assigned by Render/Cloud, defaulting to 8000 locally
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
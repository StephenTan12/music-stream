from fastapi import HTTPException

_INCLUDED_CHARACTERS = {"_", "-"}

def validate_video_id(video_id: str) -> None:
    if not video_id:
        raise HTTPException(status_code=400, detail="video_id must contain a value")
    for char in video_id:
        if char.isalnum() or char in _INCLUDED_CHARACTERS:
            continue
        raise HTTPException(status_code=400, detail="Input contains non-alphanumeric characters")

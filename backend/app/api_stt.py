from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .storage import append_log, ensure_session_dirs, get_session_paths
from .stt import SttError, transcribe_file


router = APIRouter()


class SttOut(BaseModel):
    sessionId: str
    text: str


@router.post("/api/stt", response_model=SttOut)
async def stt(
    sessionId: str = Form(...),
    audio: UploadFile = File(...),
    filename: Optional[str] = Form(None),
):
    sp = get_session_paths(sessionId)
    ensure_session_dirs(sp)

    suffix = Path(filename or audio.filename or "user.webm").suffix or ".webm"
    in_path = sp.user_dir / f"stt_upload{suffix}"
    in_path.write_bytes(await audio.read())

    append_log(
        sp,
        {
            "type": "stt_upload",
            "path": str(in_path),
            "content_type": audio.content_type,
        },
    )

    try:
        result = transcribe_file(in_path)
        append_log(sp, {"type": "stt_result", "text": result.text, "language": result.language})
        return SttOut(sessionId=sessionId, text=result.text)
    except SttError as e:
        raise HTTPException(status_code=500, detail=str(e))


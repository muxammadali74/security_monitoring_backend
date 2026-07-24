from fastapi import APIRouter, HTTPException, status, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session 
from sqlalchemy import select
import asyncio

from app.database import get_db
from app.models import UserCamerasTable as Camera
from app.services import stream_manager
from app.utils.jwt_handler import decode_access_token


router = APIRouter(
    prefix="/cameras",
    tags=['cameras']
)

@router.post('/{camera_id}/start')
async def start_camera_monitoring(camera_id:int, db: Session= Depends(get_db)):

    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID {camera_id} not found in the database"

        )
    started = stream_manager.start_stream(camera_id=camera.id, rtsp_url=camera.url)

    if not started:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Monitoring for camera {camera_id} is already running."
        )
    
    return {
        "status": "success",
        "message": f"Background stream for camera '{camera_id}' successfully started"
    }


@router.post("/{camera_id}/stop")
async def stop_camera_monitoring(camera_id:int, db:Session = Depends(get_db)):
    result = await db.execute(select(Camera).filter(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID {camera_id} not found."
        )
    
    stopped = stream_manager.stop_stream(camera_id=camera.id)

    if not stopped:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The stream for camera {camera_id} was not started"
        )
    
    return {
        "status": "success",
        "message": f"The background stream for camera '{camera.name or camera_id}' has been successfully stopped."
    }


@router.get("/active-streams")
async def get_active_streams():
    active_ids = stream_manager.get_active_streams()
    return {
        "active_camera_ids": active_ids,
        "total_active": len(active_ids)
    }


# Кадры на секунду, которые отправляются КОНКРЕТНОМУ подключённому клиенту.
# Может отличаться от STREAM_FPS в stream_manager — там частота, с которой
# кадр кладётся в буфер, здесь — с которой мы его оттуда забираем и шлём.
WS_SEND_FPS = 12
WS_SEND_INTERVAL = 1.0 / WS_SEND_FPS


@router.websocket("/{camera_id}/ws")
async def camera_stream_ws(websocket: WebSocket, camera_id: int, token: str | None = None):
    # Браузерный WebSocket API не даёт выставлять свои заголовки (в т.ч.
    # Authorization), поэтому JWT передаём как query-параметр:
    # ws://.../api/v1/cameras/{id}/ws?token=<access_token>
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return

    try:
        decode_access_token(token)
    except Exception:
        await websocket.close(code=4401, reason="Invalid or expired token")
        return

    if not stream_manager.is_active(camera_id):
        await websocket.close(code=4404, reason="Stream is not running")
        return

    await websocket.accept()

    last_sent_frame = None
    try:
        while True:
            frame_bytes = stream_manager.get_latest_frame(camera_id)

            # Шлём кадр, только если он реально новый — экономим трафик,
            # если камера ещё не успела прислать первый кадр или "зависла".
            if frame_bytes is not None and frame_bytes is not last_sent_frame:
                await websocket.send_bytes(frame_bytes)
                last_sent_frame = frame_bytes

            if not stream_manager.is_active(camera_id):
                await websocket.close(code=4404, reason="Stream was stopped")
                break

            await asyncio.sleep(WS_SEND_INTERVAL)

    except WebSocketDisconnect:
        pass
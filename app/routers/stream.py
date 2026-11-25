import asyncio
from fastapi import APIRouter, HTTPException, status, Depends, WebSocket, WebSocketDisconnect
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.camera_info import (
    ZoneCreateSchema,
    ZoneResponseSchema,
    ZoneUpdateSchema,
)
from app.models.cameras_model  import UserCamerasTable, CamerasZoneTable
from app.database import get_db
from app.database.connection import async_session
from app.models import UserCamerasTable as Camera
from app.models.user_model import UserTable
from app.dependencies.auth import get_current_user
from app.services.alert_processor import alert_processor
from app.services.stream import stream_manager
from app.utils.jwt_handler import decode_access_token


router = APIRouter(
    prefix="/stream",
    tags=['stream']
)


def _zone_data(zone: CamerasZoneTable, user_id: int) -> dict:
    return {
        "id": zone.id,
        "user_id": user_id,
        "name": zone.name,
        "zone_type": zone.zone_type,
        "color": zone.color,
        "coordinates": zone.coordinates,
        "object_class_ids": zone.object_class_ids,
        "is_active": zone.is_active,
    }


async def _load_owned_zones(
    db: AsyncSession, camera_id: int, user_id: int
) -> list[CamerasZoneTable]:
    result = await db.execute(
        select(CamerasZoneTable)
        .join(UserCamerasTable)
        .where(
            CamerasZoneTable.camera_id == camera_id,
            UserCamerasTable.user_id == user_id,
        )
        .order_by(CamerasZoneTable.id)
    )
    return list(result.scalars().all())


async def _refresh_running_camera_zones(
    db: AsyncSession, camera_id: int, user_id: int
) -> None:
    zones = await _load_owned_zones(db, camera_id, user_id)
    stream_manager.update_zones(
        camera_id,
        [_zone_data(zone, user_id) for zone in zones if zone.is_active],
    )


async def _create_zone(
    zone_data: ZoneCreateSchema,
    db: AsyncSession,
    current_user: UserTable,
) -> CamerasZoneTable:
    camera = await db.scalar(
        select(UserCamerasTable).where(
            UserCamerasTable.id == zone_data.camera_id,
            UserCamerasTable.user_id == current_user.id,
        )
    )
    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID {zone_data.camera_id} not found.",
        )

    zone = CamerasZoneTable(
        camera_id=camera.id,
        name=zone_data.name.strip(),
        zone_type=zone_data.zone_type,
        color=zone_data.color,
        coordinates=[point.model_dump() for point in zone_data.coordinates],
        object_class_ids=zone_data.object_class_ids,
        is_active=zone_data.is_active,
    )
    db.add(zone)
    await db.commit()
    await db.refresh(zone)
    await _refresh_running_camera_zones(db, camera.id, current_user.id)
    return zone


@router.post("/add_zone", response_model=ZoneResponseSchema, status_code=status.HTTP_201_CREATED)
async def add_zone(
    zone_data: ZoneCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user)
):
    return await _create_zone(zone_data, db, current_user)


@router.get("/{camera_id}/zones", response_model=list[ZoneResponseSchema])
async def list_camera_zones(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    camera = await db.scalar(
        select(UserCamerasTable).where(
            UserCamerasTable.id == camera_id,
            UserCamerasTable.user_id == current_user.id,
        )
    )
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found.")
    return await _load_owned_zones(db, camera_id, current_user.id)


@router.post(
    "/{camera_id}/zones",
    response_model=ZoneResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_camera_zone(
    camera_id: int,
    zone_data: ZoneCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    if zone_data.camera_id != camera_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="camera_id in the path and request body must match.",
        )
    return await _create_zone(zone_data, db, current_user)


@router.patch("/zones/{zone_id}", response_model=ZoneResponseSchema)
async def update_camera_zone(
    zone_id: int,
    zone_data: ZoneUpdateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    zone = await db.scalar(
        select(CamerasZoneTable)
        .join(UserCamerasTable)
        .where(
            CamerasZoneTable.id == zone_id,
            UserCamerasTable.user_id == current_user.id,
        )
    )
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found.")

    for key, value in zone_data.model_dump(exclude_unset=True).items():
        if key == "name" and value is not None:
            value = value.strip()
        if key == "coordinates" and value is not None:
            value = [point.model_dump() for point in zone_data.coordinates]
        setattr(zone, key, value)
    await db.commit()
    await db.refresh(zone)
    await _refresh_running_camera_zones(
        db, zone.camera_id, current_user.id
    )
    return zone


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera_zone(
    zone_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
) -> None:
    zone = await db.scalar(
        select(CamerasZoneTable)
        .join(UserCamerasTable)
        .where(
            CamerasZoneTable.id == zone_id,
            UserCamerasTable.user_id == current_user.id,
        )
    )
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found.")
    camera_id = zone.camera_id
    await db.delete(zone)
    await db.commit()
    await _refresh_running_camera_zones(db, camera_id, current_user.id)

@router.post('/{camera_id}/start')
async def start_stream(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user)
):

    result = await db.execute(
        select(Camera).where(Camera.id == camera_id, Camera.user_id == current_user.id)
    )
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID {camera_id} not found in the database"

        )
    zones = await _load_owned_zones(db, camera_id, current_user.id)
    started = stream_manager.start_stream(
        camera_id=camera.id,
        rtsp_url=camera.url,
        zones=[
            _zone_data(zone, current_user.id)
            for zone in zones
            if zone.is_active
        ],
        alert_callback=alert_processor.submit_from_worker,
    )

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
async def stop_stream(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user)
):
    result = await db.execute(
        select(Camera).where(Camera.id == camera_id, Camera.user_id == current_user.id)
    )
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
async def get_active_streams(
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user)
):
    active_ids = stream_manager.get_active_streams()
    if active_ids:
        result = await db.execute(
            select(Camera.id).where(
                Camera.user_id == current_user.id,
                Camera.id.in_(active_ids)
            )
        )
        owned_ids = set(result.scalars().all())
        active_ids = [camera_id for camera_id in active_ids if camera_id in owned_ids]

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
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return

    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub"))
    except (InvalidTokenError, AttributeError, TypeError, ValueError):
        await websocket.close(code=4401, reason="Invalid or expired token")
        return

    async with async_session() as db:
        result = await db.execute(
            select(Camera.id).where(
                Camera.id == camera_id,
                Camera.user_id == user_id
            )
        )
        if result.scalar_one_or_none() is None:
            await websocket.close(code=4404, reason="Camera not found")
            return

    if not stream_manager.is_active(camera_id):
        await websocket.close(code=4404, reason="Stream is not running")
        return

    await websocket.accept()

    last_sent_frame_id = None
    try:
        while True:
            metadata = stream_manager.get_latest_metadata(camera_id)

            if metadata is None:
                await asyncio.sleep(0.01)
                continue

            if metadata["frame"] is not None:
                frame_id = metadata.get("frame_id")
                frame = metadata.get("frame")
                detections = metadata.get("detections")

                if frame is not None and frame_id != last_sent_frame_id:

                    await websocket.send_json({
                        "type": "metadata",
                        "frame_id": frame_id,
                        "detections": detections,
                    })

                    await websocket.send_bytes(frame)   

                    last_sent_frame_id = frame_id

            if not stream_manager.is_active(camera_id):
                await websocket.close(code=4404, reason="Stream was stopped")
                break

            await asyncio.sleep(WS_SEND_INTERVAL)

    except WebSocketDisconnect:
        pass
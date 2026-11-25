from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.dependencies.auth import get_current_user
from app.models.cameras_model import CamerasZoneTable, UserCamerasTable
from app.models.security_event_model import DetectionEventTable
from app.models.user_model import UserTable
from app.schemas.security_schemas import DetectionEventResponse
from config import settings

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/", response_model=list[DetectionEventResponse])
async def list_events(
    camera_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    query = (
        select(DetectionEventTable, UserCamerasTable.name, CamerasZoneTable.name)
        .join(UserCamerasTable, DetectionEventTable.camera_id == UserCamerasTable.id)
        .outerjoin(
            CamerasZoneTable, DetectionEventTable.zone_id == CamerasZoneTable.id
        )
        .where(DetectionEventTable.user_id == current_user.id)
        .order_by(
            DetectionEventTable.occurred_at.desc(), DetectionEventTable.id.desc()
        )
        .limit(limit)
    )
    if camera_id is not None:
        query = query.where(DetectionEventTable.camera_id == camera_id)

    rows = (await db.execute(query)).all()
    return [
        DetectionEventResponse(
            id=event.id,
            camera_id=event.camera_id,
            camera_name=camera_name or f"Camera {event.camera_id}",
            zone_id=event.zone_id,
            zone_name=zone_name,
            object_class_id=event.object_class_id,
            confidence=event.confidence,
            bounding_box=event.bounding_box,
            occurred_at=event.occurred_at,
            notification_status=event.notification_status,
            snapshot_url=f"{settings.API_V1_STR}/events/{event.id}/snapshot",
        )
        for event, camera_name, zone_name in rows
    ]


@router.get("/{event_id}/snapshot")
async def get_event_snapshot(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user),
):
    event = await db.scalar(
        select(DetectionEventTable).where(
            DetectionEventTable.id == event_id,
            DetectionEventTable.user_id == current_user.id,
        )
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Event snapshot not found.")
    return Response(
        content=event.snapshot,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, no-store"},
    )

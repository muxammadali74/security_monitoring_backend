from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.concurrency import run_in_threadpool

from app.schemas.camera_info import NewCamera, CameraResponse, PreviewRequestSchema, PreviewResponseSchema
from app.database.connection import get_db
from app.models.cameras_model import UserCamerasTable
from app.models.user_model import UserTable
from app.dependencies.auth import get_current_user
from app.utils.camera_helper import capture_single_frame
from app.services.stream import stream_manager

router = APIRouter(
    prefix="/newstream",
    tags=["stream"]
)

@router.get("/", response_model=list[CameraResponse])
async def list_cameras(
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user)
):
    result = await db.execute(
        select(UserCamerasTable)
        .where(UserCamerasTable.user_id == current_user.id)
        .order_by(UserCamerasTable.id)
    )
    return result.scalars().all()


@router.post("/", response_model=CameraResponse)
async def new_stream(
    new_camera_info: NewCamera,
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user)
):
    try:
        new_camera = UserCamerasTable( 
            user_id=current_user.id,
            name=new_camera_info.name,
            url=new_camera_info.url 
        )

        db.add(new_camera)
        await db.commit()
        await db.refresh(new_camera)

        return new_camera

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding camera: {e}"
        )
    

@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(
    camera_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: UserTable = Depends(get_current_user)
) -> None:
    result = await db.execute(
        select(UserCamerasTable).where(
            UserCamerasTable.id == camera_id,
            UserCamerasTable.user_id == current_user.id
        )
    )
    camera = result.scalar_one_or_none()
    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera with ID {camera_id} not found."
        )

    if stream_manager.is_active(camera_id):
        stream_manager.stop_stream(camera_id)

    await db.delete(camera)
    await db.commit()


@router.post("/preview", response_model=PreviewResponseSchema)
async def get_stream_preview(
    body: PreviewRequestSchema,
    current_user: UserTable = Depends(get_current_user)
):
    result = await run_in_threadpool(capture_single_frame, body.rtsp_url)
    
    return PreviewResponseSchema(
        image_base64=result["image_base64"],
        width=result["width"],
        height=result["height"]
    )



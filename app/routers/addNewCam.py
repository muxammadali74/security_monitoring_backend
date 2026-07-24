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

router = APIRouter(
    prefix="/newcam",
    tags=["cameras"] 
)


@router.post("/", response_model=CameraResponse)
async def add_new_camera(
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
    

@router.post("/preview", response_model=PreviewResponseSchema)
async def get_camera_preview(
    body: PreviewRequestSchema,
    current_user: UserTable = Depends(get_current_user)
):
    result = await run_in_threadpool(capture_single_frame, body.rtsp_url)
    
    return PreviewResponseSchema(
        image_base64=result["image_base64"],
        width=result["width"],
        height=result["height"]
    )



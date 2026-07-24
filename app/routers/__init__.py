from fastapi import APIRouter

from .auth import router as auth_router
from .registration import router as registration_router
from .addNewCam import router as addnewcam
from .cameras import router as cameras

router = APIRouter()
router.include_router(registration_router)
router.include_router(auth_router)
router.include_router(addnewcam)
router.include_router(cameras)

__all__ = ["router"]

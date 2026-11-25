from fastapi import APIRouter

from .auth import router as auth_router
from .registration import router as registration_router
from .addNewCam import router as addnewcam
from .stream import router as stream
from .dashboard import router as dashboard
from .events import router as events
from .telegram import router as telegram

router = APIRouter()
router.include_router(registration_router)
router.include_router(auth_router)
router.include_router(addnewcam)
router.include_router(stream)
router.include_router(dashboard)
router.include_router(events)
router.include_router(telegram)

__all__ = ["router"]

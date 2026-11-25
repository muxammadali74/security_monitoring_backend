from fastapi import APIRouter, HTTPException, status 


from app.services.stream import stream_manager

router = APIRouter(
    prefix="/dashboard",
    tags=["statistics"]
)

@router.get("/statistics")
async def get_system_statistics():
    active_streams = stream_manager.get_active_streams()
    total_streams = 0
    events_today = 0
    return {
        "active_streams": active_streams,
        "total_streams": total_streams, 
        "events_today": events_today
    }


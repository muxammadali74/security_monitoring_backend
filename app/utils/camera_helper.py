import cv2 
import base64
from fastapi import HTTPException, status

def capture_single_frame(rtsp_url:str) -> dict:
    cap = cv2.VideoCapture(rtsp_url)

    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)

    if not cap.isOpened():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to connect to the RTSP stream. Check the link or the camera status"
        )
    
    try:
        ret, frame = cap.read()

        if not ret or frame is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="The stream is open, but the frame could not be read (possibly an empty stream)"
            )
        
        height, width, _ = frame.shape

        success, encoded_image = cv2.imencode('.jpg', frame)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="JPEG frame encoding error."
            )

        base64_bytes = base64.b64encode(encoded_image)
        base64_string = base64_bytes.decode('utf-8')

        return {
            "image_base64": base64_string,
            "width": width,
            "height": height
        }
    
    finally:
        cap.release()
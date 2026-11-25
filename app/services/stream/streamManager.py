import threading
import time
import logging
import cv2
from ultralytics import YOLO 
from collections import defaultdict

from .cameraWorker import CameraWorker
from .detector import Detector

logger = logging.getLogger("stream_manager")
logging.basicConfig(level=logging.INFO)


JPEG_QUALITY = 70

STREAM_FPS = 12
STREAM_FRAME_INTERVAL = 1.0 / STREAM_FPS


class StreamManager():
    def __init__(self):
        self._active_streams = {}
        self._lock = threading.Lock()
        self._latest_metadata = {}
        self._frames_lock = threading.Lock()
        self.detector= Detector()
        self._frame_ids = defaultdict(int)


    def _set_latest_metadata(self, camera_id: int, frame, detections) -> None:
        ok, encoded = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        )

        if not ok:
            return
        with self._frames_lock:
            self._frame_ids[camera_id]+=1

            frame_id = self._frame_ids[camera_id]

            self._latest_metadata[camera_id] = {
                 "frame_id": frame_id,
                 "frame": encoded.tobytes(),
                 "detections": detections
            }

    def get_latest_metadata(self, camera_id: int) -> dict | None:
        with self._frames_lock:
            return self._latest_metadata.get(camera_id)

    def _clear_latest_metadata(self, camera_id: int) -> None:
        with self._frames_lock:
            self._latest_metadata.pop(camera_id, None)
            self._frame_ids.pop(camera_id, None)

    def start_stream(
        self,
        camera_id: int,
        rtsp_url: str,
        zones: list | None = None,
        alert_callback=None,
    ) -> bool:

        with self._lock:

            if camera_id in self._active_streams:
                logger.warning(f"[Камера {camera_id}] Уже запущена. Повторный запуск отклонен.")
                return False

            stop_event = threading.Event()

            worker = CameraWorker(
                rtsp_url=rtsp_url,
                camera_id=camera_id,
                stop_event=stop_event,
                detector=self.detector,
                metadata_callback=self._set_latest_metadata,
                zones=zones,
                alert_callback=alert_callback,
            )

            thread = threading.Thread(
                target=worker.run,
                name=f"CameraThread_{camera_id}",
                daemon=True
            )
            self._active_streams[camera_id] = {
            "thread": thread,
            "stop_event": stop_event,
            "worker": worker,
            }

            thread.start()

            return True

    def update_zones(self, camera_id: int, zones: list) -> None:
        with self._lock:
            stream = self._active_streams.get(camera_id)
            if stream is not None:
                stream["worker"].update_zones(zones)

    def stop_stream(self, camera_id: int) -> bool:
        with self._lock:
            if camera_id not in self._active_streams:
                logger.warning(f"[Camera {camera_id}] Not found in the list of active streams")
                return False

            stream = self._active_streams[camera_id]
            stream["stop_event"].set()
            del self._active_streams[camera_id]

        stream["thread"].join(timeout=2)
        self._clear_latest_metadata(camera_id)
        return True

    def stop_all(self) -> None:
        for camera_id in self.get_active_streams():
            self.stop_stream(camera_id)
    

    def get_active_streams(self) -> list:
        with self._lock:
            return list(self._active_streams.keys())

    def is_active(self, camera_id: int) -> bool:
        with self._lock:
            return camera_id in self._active_streams


stream_manager = StreamManager()

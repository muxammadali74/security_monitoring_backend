import threading
import time
import logging
import cv2
from ultralytics import YOLO 

logger = logging.getLogger("stream_manager")
logging.basicConfig(level=logging.INFO)


JPEG_QUALITY = 70

STREAM_FPS = 12
STREAM_FRAME_INTERVAL = 1.0 / STREAM_FPS


class StreamManager():
    def __init__(self):
        self._active_streams = {}
        self._lock = threading.Lock()
        self._latest_frames = {}
        self._frames_lock = threading.Lock()
        self.model = YOLO('yolov8n.pt')
        self.model.fuse()

    def _set_latest_frame(self, camera_id: int, frame) -> None:
        ok, encoded = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        )
        if not ok:
            return
        with self._frames_lock:
            self._latest_frames[camera_id] = encoded.tobytes()

    def get_latest_frame(self, camera_id: int) -> bytes | None:
        with self._frames_lock:
            return self._latest_frames.get(camera_id)

    def _clear_latest_frame(self, camera_id: int) -> None:
        with self._frames_lock:
            self._latest_frames.pop(camera_id, None)

    def _camera_worker(self, camera_id: int, rtsp_url: str, stop_envent: threading.Event):
        logger.info(f"[Camera {camera_id}] Background stream successfully STARTED.")

        cap = cv2.VideoCapture(rtsp_url)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)

        frame_counter = 0
        last_stream_ts = 0.0

        try:
            while not stop_envent.is_set():
                if not cap.isOpened():
                    logger.warning(f"[Camera {camera_id}] Connection lost. Reconnecting in 5 seconds...")
                    time.sleep(5)
                    cap = cv2.VideoCapture(rtsp_url)
                    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
                    continue

                ret, frame = cap.read()
                if not ret or frame is None:
                    logger.warning(f"[Camera {camera_id}] Failed to recover frame. Skipping...")
                    time.sleep(0.05)
                    continue

                frame_counter += 1
                if frame_counter % 3 == 0:
                    logger.info(f"[Camera {camera_id}] Processed frame #{frame_counter}. Resolution: {frame.shape[1]}x{frame.shape[0]}")



                    results = self.model(frame, 
                                         classes=[0,2,7],  
                                         conf=0.5,
                                         verbose=False,
                                         max_det=20)
                    frame = results[0].plot()




                now = time.monotonic()
                if now - last_stream_ts >= STREAM_FRAME_INTERVAL:
                    self._set_latest_frame(camera_id, frame)
                    last_stream_ts = now

                time.sleep(0.01)

        except Exception as e:
            logger.error(f"[Camera {camera_id}] Critical error in stream: {e}")

        finally:
            cap.release()
            self._clear_latest_frame(camera_id)
            logger.info(f"[Camera {camera_id}] Stream STOPPED, camera resources released.")

    def start_stream(self, camera_id: int, rtsp_url: str) -> bool:
        with self._lock:
            if camera_id in self._active_streams:
                logger.warning(f"[Камера {camera_id}] Уже запущена. Повторный запуск отклонен.")
                return False

            stop_event = threading.Event()

            thread = threading.Thread(
                target=self._camera_worker,
                args=(camera_id, rtsp_url, stop_event),
                name=f"CameraThread_{camera_id}",
                daemon=True
            )
            self._active_streams[camera_id] = {
                "thread": thread,
                "stop_event": stop_event
            }
            thread.start()
            return True

    def stop_stream(self, camera_id: int) -> bool:
        with self._lock:
            if camera_id not in self._active_streams:
                logger.warning(f"[Camera {camera_id}] Not found in the list of active streams")
                return False

            self._active_streams[camera_id]["stop_event"].set()

            del self._active_streams[camera_id]

        self._clear_latest_frame(camera_id)
        return True

    def get_active_streams(self) -> list:
        with self._lock:
            return list(self._active_streams.keys())

    def is_active(self, camera_id: int) -> bool:
        with self._lock:
            return camera_id in self._active_streams


stream_manager = StreamManager()

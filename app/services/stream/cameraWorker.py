import cv2
import threading
import logging
import time
import numpy as np
from datetime import datetime, timezone

from .detector import Detector
from .zone import ZoneEngine
from app.utils.event_tracker import ZoneEventTracker


logger = logging.getLogger("camera_worker")

JPEG_QUALITY = 70

STREAM_FPS = 12
STREAM_FRAME_INTERVAL = 1.0 / STREAM_FPS

class CameraWorker():
    def __init__(self, 
                 rtsp_url: str, 
                 camera_id: int, 
                 stop_event:threading.Event, 
                 detector, 
                 metadata_callback=None,
                 zones: list = None,
                 alert_callback=None):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.stop_event = stop_event
        self.detector = detector
        self.metadata_callback = metadata_callback
        self.zoneEngine = ZoneEngine(zones)
        self.event_tracker = ZoneEventTracker()
        self.alert_callback = alert_callback

    def update_zones(self, zones: list) -> None:
        self.zoneEngine.set_zones(zones)
        self.event_tracker.reset()

    def _create_alert_snapshot(self, frame, detection, zone):
        annotated = frame.copy()
        height, width = frame.shape[:2]
        polygon = [
            (round(point["x"] * width), round(point["y"] * height))
            for point in zone["coordinates"]
        ]
        cv2.polylines(
            annotated,
            [np.array(polygon, dtype=np.int32)],
            True,
            (0, 220, 255),
            2,
        )
        x1, y1, x2, y2 = (
            round(float(detection[key])) for key in ("x1", "y1", "x2", "y2")
        )
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (66, 211, 146), 2)
        label = f"class {detection['class_id']} {detection['confidence']:.0%}"
        cv2.putText(
            annotated,
            label,
            (max(0, x1), max(18, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (66, 211, 146),
            2,
        )
        encoded_ok, encoded = cv2.imencode(
            ".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80]
        )
        if not encoded_ok:
            raise RuntimeError("Could not encode the security alert snapshot.")
        return encoded.tobytes()

    def run(self):
        logger.info(
            f"[Camera {self.camera_id}] "
            "Background stream successfully STARTED."
        )

        cap = cv2.VideoCapture(self.rtsp_url)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)

        frame_counter = 0
        last_stream_ts = 0.0

        try:
            while not self.stop_event.is_set():
                if not cap.isOpened():
                    logger.warning(
                        f"[Camera {self.camera_id}] "
                        "Connection lost. Reconnecting in 5 seconds..."
                    )
                    time.sleep(5)
                    cap = cv2.VideoCapture(self.rtsp_url)
                    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)

                    continue

                ret, frame = cap.read()

                if not ret or frame is None:
                    logger.warning(
                        f"[Camera {self.camera_id}] "
                        "Failed to recover frame. Skipping..."
                    )

                    time.sleep(5)
                    continue

                if frame_counter % 3 ==0:
                    logger.info(
                        f"[Camera {self.camera_id}] "
                        f"Processed frame #{frame_counter}. "
                        f"Resolution: "
                        f"{frame.shape[1]}x{frame.shape[0]}"
                    )
                    
                    detections = self.detector.process(frame)
                    zones = self.zoneEngine.get_zones()
                    alerts = self.event_tracker.update(
                        detections, zones, frame.shape
                    )

                    for det in detections:
                        matched_zones = self.zoneEngine.zones_for_detection(
                            det, frame.shape
                        )
                        det["zone_ids"] = [zone["id"] for zone in matched_zones]
                        det["in_zone"] = bool(matched_zones)

                    for alert in alerts:
                        if self.alert_callback is None:
                            continue
                        try:
                            zone = alert["zone"]
                            detection = alert["detection"]
                            self.alert_callback(
                                {
                                    "user_id": zone["user_id"],
                                    "camera_id": self.camera_id,
                                    "zone_id": zone["id"],
                                    "zone_name": zone["name"],
                                    "zone_type": zone["zone_type"],
                                    "object_class_id": detection["class_id"],
                                    "confidence": detection["confidence"],
                                    "bounding_box": {
                                        key: float(detection[key])
                                        for key in ("x1", "y1", "x2", "y2")
                                    },
                                    "snapshot": self._create_alert_snapshot(
                                        frame, detection, zone
                                    ),
                                    "occurred_at": datetime.now(timezone.utc),
                                }
                            )
                        except Exception:
                            logger.exception(
                                "[Camera %s] Failed to queue zone alert.",
                                self.camera_id,
                            )
                    
                else: 
                    detections = None

                
                now = time.monotonic()
                if now - last_stream_ts >= STREAM_FRAME_INTERVAL:
                    self.metadata_callback(self.camera_id, frame, detections)
                    last_stream_ts = now

                time.sleep(0.01)    
                frame_counter+=1


        except Exception as e:
             logger.error(
                f"[Camera {self.camera_id}] "
                f"Critical error in stream: {e}"
            )

        finally:
            cap.release()
            logger.info(
                f"[Camera {self.camera_id}] "
                "Stream STOPPED, camera resources released."
            )

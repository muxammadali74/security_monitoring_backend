from ultralytics import YOLO
import torch
from .zone import ZoneEngine

class Detector:
    def __init__(self):
        self.model = YOLO('yolov8n.pt')
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(device)
        self.model.fuse()
        

    def process(self, frame):
        detections = []

        results = self.model(
            frame,
            classes=[0, 2, 7],
            conf=0.5,
            verbose=False,
            max_det=20,
        )

        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                detections.append({
                "class_id": int(box.cls[0]),
                "confidence": float(box.conf[0]),
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                })

        return detections
    
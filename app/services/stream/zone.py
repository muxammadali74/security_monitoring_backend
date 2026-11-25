from threading import Lock

from app.utils.geometry import point_in_polygon

class ZoneEngine:
    def __init__(self, zones):
        self._zones = list(zones or [])
        self._lock = Lock()

    def set_zones(self, zones):
        with self._lock:
            self._zones = list(zones or [])

    def get_zones(self):
        with self._lock:
            return list(self._zones)

    def zones_for_detection(self, detection, frame_shape):
        height, width = frame_shape[:2]
        point = (
            (float(detection["x1"]) + float(detection["x2"])) / (2 * width),
            float(detection["y2"]) / height,
        )
        class_id = int(detection["class_id"])
        matches = []

        for zone in self.get_zones():
            if not zone.get("is_active", True):
                continue
            if class_id not in zone.get("object_class_ids", []):
                continue
            polygon = [(point["x"], point["y"]) for point in zone["coordinates"]]
            if point_in_polygon(point, polygon):
                matches.append(zone)

        return matches

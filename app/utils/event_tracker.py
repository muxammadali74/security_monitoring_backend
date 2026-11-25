from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Any

from app.utils.geometry import bbox_iou, point_in_polygon


@dataclass
class _Track:
    class_id: int
    bbox: tuple[float, float, float, float]
    last_seen: float
    zone_ids: set[int] = field(default_factory=set)


class ZoneEventTracker:
    def __init__(self, track_ttl_seconds: float = 2.0, iou_threshold: float = 0.25):
        self.track_ttl_seconds = track_ttl_seconds
        self.iou_threshold = iou_threshold
        self._tracks: list[_Track] = []

    def reset(self) -> None:
        self._tracks.clear()

    def update(
        self,
        detections: list[dict[str, Any]],
        zones: list[dict[str, Any]],
        frame_shape: tuple[int, ...],
        timestamp: float | None = None,
    ) -> list[dict[str, Any]]:
        now = monotonic() if timestamp is None else timestamp
        self._tracks = [
            track
            for track in self._tracks
            if now - track.last_seen <= self.track_ttl_seconds
        ]
        used_tracks: set[int] = set()
        alerts: list[dict[str, Any]] = []
        height, width = frame_shape[:2]

        for detection in detections:
            class_id = int(detection["class_id"])
            bbox = tuple(
                float(detection[key]) for key in ("x1", "y1", "x2", "y2")
            )
            best_index = None
            best_iou = self.iou_threshold
            for index, track in enumerate(self._tracks):
                if index in used_tracks or track.class_id != class_id:
                    continue
                overlap = bbox_iou(bbox, track.bbox)
                if overlap >= best_iou:
                    best_iou = overlap
                    best_index = index

            if best_index is None:
                track = _Track(class_id=class_id, bbox=bbox, last_seen=now)
                self._tracks.append(track)
                best_index = len(self._tracks) - 1
            else:
                track = self._tracks[best_index]
                track.bbox = bbox
                track.last_seen = now

            used_tracks.add(best_index)
            foot_point = ((bbox[0] + bbox[2]) / (2 * width), bbox[3] / height)
            matching_zones = [
                zone
                for zone in zones
                if zone.get("is_active", True)
                and class_id in zone.get("object_class_ids", [])
                and point_in_polygon(
                    foot_point,
                    [
                        (float(point["x"]), float(point["y"]))
                        for point in zone["coordinates"]
                    ],
                )
            ]
            current_zone_ids = {int(zone["id"]) for zone in matching_zones}

            for zone in matching_zones:
                if int(zone["id"]) not in track.zone_ids:
                    alerts.append({"zone": zone, "detection": detection})

            track.zone_ids = current_zone_ids
            detection["zone_ids"] = sorted(current_zone_ids)
            detection["in_zone"] = bool(current_zone_ids)

        return alerts

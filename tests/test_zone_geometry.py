import unittest

from app.utils.event_tracker import ZoneEventTracker
from app.utils.geometry import bbox_iou, point_in_polygon, validate_polygon


class PolygonValidationTests(unittest.TestCase):
    def test_accepts_valid_normalized_polygon(self):
        validate_polygon([(0.1, 0.1), (0.8, 0.1), (0.7, 0.8), (0.2, 0.7)])

    def test_rejects_self_intersecting_polygon(self):
        with self.assertRaisesRegex(ValueError, "must not intersect"):
            validate_polygon([(0.1, 0.1), (0.9, 0.9), (0.1, 0.9), (0.9, 0.1)])

    def test_boundary_counts_as_inside(self):
        self.assertTrue(
            point_in_polygon(
                (0.5, 0.1),
                [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)],
            )
        )

    def test_iou_of_identical_boxes_is_one(self):
        self.assertEqual(bbox_iou((0, 0, 10, 10), (0, 0, 10, 10)), 1.0)


class ZoneEventTrackerTests(unittest.TestCase):
    def setUp(self):
        self.tracker = ZoneEventTracker()
        self.zones = [
            {
                "id": 5,
                "name": "Entrance",
                "coordinates": [
                    {"x": 0.2, "y": 0.2},
                    {"x": 0.8, "y": 0.2},
                    {"x": 0.8, "y": 0.9},
                    {"x": 0.2, "y": 0.9},
                ],
                "object_class_ids": [0],
                "is_active": True,
            }
        ]
        self.detection = {
            "class_id": 0,
            "confidence": 0.9,
            "x1": 15,
            "y1": 30,
            "x2": 35,
            "y2": 80,
        }

    def test_emits_once_for_repeated_detections_in_same_zone(self):
        first = self.tracker.update(
            [dict(self.detection)], self.zones, (100, 100, 3), timestamp=1.0
        )
        second = self.tracker.update(
            [dict(self.detection)], self.zones, (100, 100, 3), timestamp=1.1
        )
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])

    def test_emits_again_after_detected_exit_and_reentry(self):
        self.tracker.update(
            [dict(self.detection)], self.zones, (100, 100, 3), timestamp=1.0
        )
        outside = dict(self.detection, x1=5, x2=25, y2=80)
        self.tracker.update([outside], self.zones, (100, 100, 3), timestamp=1.1)
        entered = self.tracker.update(
            [dict(self.detection)], self.zones, (100, 100, 3), timestamp=1.2
        )
        self.assertEqual(len(entered), 1)

    def test_ignores_detections_of_unselected_classes(self):
        other_class = dict(self.detection, class_id=2)
        alerts = self.tracker.update(
            [other_class], self.zones, (100, 100, 3), timestamp=1.0
        )
        self.assertEqual(alerts, [])

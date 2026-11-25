import unittest

from pydantic import ValidationError

from app.schemas.camera_info import ZoneCreateSchema, ZoneUpdateSchema


class ZoneSchemaTests(unittest.TestCase):
    def setUp(self):
        self.valid_zone = {
            "camera_id": 12,
            "name": "Entrance",
            "coordinates": [
                {"x": 0.1, "y": 0.1},
                {"x": 0.9, "y": 0.1},
                {"x": 0.5, "y": 0.9},
            ],
        }

    def test_create_rejects_whitespace_name(self):
        with self.assertRaises(ValidationError):
            ZoneCreateSchema(**{**self.valid_zone, "name": "  "})

    def test_create_rejects_unsupported_object_class(self):
        with self.assertRaises(ValidationError):
            ZoneCreateSchema(
                **{**self.valid_zone, "object_class_ids": [1]}
            )

    def test_update_rejects_explicit_null_for_non_nullable_fields(self):
        with self.assertRaises(ValidationError):
            ZoneUpdateSchema(name=None)

    def test_update_rejects_whitespace_name(self):
        with self.assertRaises(ValidationError):
            ZoneUpdateSchema(name="  ")


if __name__ == "__main__":
    unittest.main()

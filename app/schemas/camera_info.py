from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.utils.geometry import validate_polygon

class NewCamera(BaseModel):
    name: str
    url: str

class CameraResponse(BaseModel):
    id: int
    user_id: int
    name: str 
    url: str

    class Config:
        from_attributes = True

class PreviewRequestSchema(BaseModel):
    rtsp_url: str

class PreviewResponseSchema(BaseModel):
    image_base64: str
    width: int
    height: int

class PointSchema(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0, description="Нормализованная координата X (0.0 - 1.0)")
    y: float = Field(..., ge=0.0, le=1.0, description="Нормализованная координата Y (0.0 - 1.0)")


class ZoneCreateSchema(BaseModel):
    camera_id: int
    name: str = Field(..., min_length=1, max_length=100, example="Зона въезда")
    zone_type: str = Field(
        default="intrusion",
        pattern="^(intrusion|detection|restricted|monitoring)$",
        example="restricted",
    )
    color: str = Field(default="indigo", pattern="^(indigo|cyan|amber|red)$")
    coordinates: list[PointSchema] = Field(
        ...,
        min_length=3,
        max_length=64,
        description="Массив точек полигона (минимум 3 точки)"
    )
    object_class_ids: list[int] = Field(default_factory=lambda: [0, 2, 7], min_length=1)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_coordinates(self):
        if not self.name.strip():
            raise ValueError("Zone name cannot be empty.")
        validate_polygon([(point.x, point.y) for point in self.coordinates])
        if any(class_id not in {0, 2, 7} for class_id in self.object_class_ids):
            raise ValueError("Supported object classes are person (0), car (2), and truck (7).")
        return self


class ZoneUpdateSchema(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    zone_type: str | None = Field(
        default=None,
        pattern="^(intrusion|detection|restricted|monitoring)$",
    )
    color: str | None = Field(default=None, pattern="^(indigo|cyan|amber|red)$")
    coordinates: list[PointSchema] | None = Field(default=None, min_length=3, max_length=64)
    object_class_ids: list[int] | None = Field(default=None, min_length=1)
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_values(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")
        if self.name is not None and not self.name.strip():
            raise ValueError("Zone name cannot be empty.")
        if self.coordinates is not None:
            validate_polygon([(point.x, point.y) for point in self.coordinates])
        if self.object_class_ids is not None and any(
            class_id not in {0, 2, 7} for class_id in self.object_class_ids
        ):
            raise ValueError("Supported object classes are person (0), car (2), and truck (7).")
        return self


class ZoneResponseSchema(BaseModel):
    id: int
    camera_id: int
    name: str
    zone_type: str
    color: str
    coordinates: list[PointSchema]
    object_class_ids: list[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
from pydantic import BaseModel

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
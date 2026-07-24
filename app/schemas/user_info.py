from pydantic import BaseModel, EmailStr, Field, model_validator

class UserRegisterSchema(BaseModel):
    name: str
    email: EmailStr
    password: str
    repeat_password: str = Field(..., validation_alias="repeat_password")

    @model_validator(mode="after")
    def check_passwords_match(self) -> "UserRegisterSchema":
        if self.password != self.repeat_password:
            raise ValueError("Passwords do not match.")
        return self


class UserAuthSchema(BaseModel):
    email: EmailStr
    password: str


class UserPublicSchema(BaseModel):
    id: int
    name: str
    email: EmailStr

    model_config = {"from_attributes": True}


class TokenSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"

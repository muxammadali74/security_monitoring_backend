from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.models.user_model import UserTable
from app.schemas import TokenSchema, UserAuthSchema
from app.utils.jwt_handler import create_access_token
from app.utils.password_hash import verify_password

router = APIRouter(
    prefix="/login",
    tags=["authorization"],
)


@router.post("", response_model=TokenSchema)
async def login(
    # user_data: UserAuthSchema,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    # query = select(UserTable).where(UserTable.email == user_data.email)
    # result = await db.execute(query)
    # user = result.scalar_one_or_none()

    query = select(UserTable).where(UserTable.email == form_data.username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    token_payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,          
        "is_admin": user.is_admin
    }

    access_token = create_access_token(token_payload)

    return TokenSchema(access_token=access_token, token_type="bearer")
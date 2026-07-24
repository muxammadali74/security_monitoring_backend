from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.models.user_model import UserTable
from app.schemas import UserPublicSchema, UserRegisterSchema
from app.utils.password_hash import hash_password
from config import settings

router = APIRouter(
    prefix="/registration",
    tags=["authorization"],
)


@router.post("", response_model=UserPublicSchema, status_code=status.HTTP_201_CREATED)
async def registration(
    user_data: UserRegisterSchema,
    db: AsyncSession = Depends(get_db),
):
    query = select(UserTable).where(UserTable.email == user_data.email)
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email is already registered",
        )

    new_user = UserTable(
        name=user_data.name,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user



@router.post("/admin", response_model=UserPublicSchema, status_code=status.HTTP_201_CREATED)
async def register_admin(
    user_data: UserRegisterSchema,
    secret_key: str, 
    db: AsyncSession = Depends(get_db),
):
    if secret_key != settings.ADMIN_REGISTRATION_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret key for admin registration",
        )

    query = select(UserTable).where(UserTable.email == user_data.email)
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email is already registered",
        )

    new_admin = UserTable(
        name=user_data.name,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        is_admin=True,
    )
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)

    return new_admin
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt 
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from config import settings
from app.database.connection import get_db
from app.models.user_model import UserTable

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")

async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
) -> UserTable:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Failed to validate credentials (invalid or expired token)",
        headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=settings.JWT_ALGORITHM)
        user_id: str = payload.get('sub')
        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception
    
    query = select(UserTable).where(UserTable.id ==int(user_id))
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    
    return user 

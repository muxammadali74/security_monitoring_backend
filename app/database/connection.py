from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings

# echo=True — удобно на этапе разработки, чтобы видеть все SQL-запросы в консоли.
# На проде лучше переключить на settings.ENVIRONMENT == "development".
engine = create_async_engine(settings.DATABASE_URL, echo=settings.ENVIRONMENT == "development")

# expire_on_commit=False нужен, чтобы объекты не "умирали" после commit()
# и их можно было использовать (например, отдавать в ответе) уже после сохранения в БД.
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session

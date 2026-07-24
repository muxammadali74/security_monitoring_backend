import sys
import asyncio

# Важно: этот фикс должен стоять ДО любых импортов, которые могут создать event loop.
# asyncpg плохо работает с ProactorEventLoop на Windows — соединения обрываются
# с ConnectionResetError / WinError 10054. SelectorEventLoop решает эту проблему.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from contextlib import asynccontextmanager


from fastapi import FastAPI

from config import settings
from app.routers import router
from app.database import check_and_create_database, init_tables
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    await check_and_create_database()
    await init_tables()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешает запросы со всех сайтов. Для разработки — ок.
    allow_credentials=True,
    allow_methods=["*"],  # Разрешает ВСЕ методы, включая OPTIONS, POST, GET и т.д.
    allow_headers=["*"],  # Разрешает любые заголовки
)

app.include_router(router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["system"])
async def health_check():
    return {"status": "ok"}

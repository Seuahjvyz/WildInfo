from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text
from app.config import settings
import asyncio
import logging
from urllib.parse import urlparse, urlunparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_async_url(url: str) -> str:
    if "+asyncpg" in url:
        return url
    
    parsed = urlparse(url)
    
    clean_parsed = parsed._replace(
        scheme="postgresql+asyncpg",
        query=""  
    )
    
    return urlunparse(clean_parsed)

ASYNC_DATABASE_URL = get_async_url(str(settings.DATABASE_URL))
logger.info(f"Conectando a Neon con URL asíncrona")

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    pool_recycle=300,
    echo=False
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    """Dependencia FastAPI para obtener una sesión asíncrona"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

def keep_alive_sync():
    try:
        import psycopg2
        
        sync_url = str(settings.DATABASE_URL)
        if "?" in sync_url:
            sync_url = sync_url.split("?")[0]
        
        conn = psycopg2.connect(sync_url)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        logger.debug(" Keep-alive ping successful")
        return True
    except Exception as e:
        logger.error(f" Keep-alive ping failed: {e}")
        return False

async def start_keep_alive_task():
    while True:
        await asyncio.sleep(settings.KEEP_ALIVE_INTERVAL_SECONDS)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, keep_alive_sync)

async def test_connection():
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT version()"))
            version = result.fetchone()
            logger.info(f" Conexión Exitosa! Versión: {version[0][:50]}...")
            return True
    except Exception as e:
        logger.error(f" Falló la conexión: {e}")
        return False
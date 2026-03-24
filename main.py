from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import test_connection, start_keep_alive_task, engine
from app.config import settings
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="WildfInfo API",
    description="API con Neon PostgreSQL (Pooled Connection)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info(" Prueba de conexion de la bd.")
    
    if await test_connection():
        logger.info(" Neon database ready")
    else:
        logger.warning(" Could not connect to Neon")
    
    asyncio.create_task(start_keep_alive_task())
    logger.info(f" Keep-alive started (every {settings.KEEP_ALIVE_INTERVAL_SECONDS} seconds)")

@app.on_event("shutdown")
async def shutdown_event():
    await engine.dispose()
    logger.info(" Database connections closed")

@app.get("/")
def root():
    return {
        "message": "WildfInfo API",
        "database": "Neon PostgreSQL (Pooled)",
        "status": "running",
        "pooled_connection": True
    }

@app.get("/health")
async def health_check():
    from app.database import AsyncSessionLocal
    from sqlalchemy import text
    
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            return {
                "status": "healthy",
                "database": "connected",
                "pooled": True
            }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "degraded",
            "database": "disconnected",
            "pooled": True,
            "error": str(e)
        }
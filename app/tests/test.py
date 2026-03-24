from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Aplicar la misma transformación que en database.py
if "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    # Eliminar parámetros de consulta
    if "?" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.split("?")[0]

print(f"Probando conexión con SQLAlchemy...")
print(f"URL: {DATABASE_URL}")

try:
    engine = create_engine(DATABASE_URL, echo=False)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        version = result.fetchone()
        print(f"✅ Conexión SQLAlchemy exitosa!")
        print(f"📦 Versión: {version[0][:60]}...")
        
        # Probar ping
        result = conn.execute(text("SELECT 1"))
        print(f"✅ Ping: {result.fetchone()[0]}")
        
except Exception as e:
    print(f"❌ Error: {e}")
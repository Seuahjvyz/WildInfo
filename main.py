from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import time
import httpx
from dotenv import load_dotenv
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Carga las variables del archivo .env al inicio
load_dotenv()

app = FastAPI(title="WildInfo")

# ------------- CONFIGURACION DE CORS ------------- #
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------- MONITOR DE CONSOLA ------- #
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    print(f"DEBUG: {request.method} {request.url.path} - Status: {response.status_code} - {process_time:.2f}ms")
    return response

# ------- FUNCIÓN PARA CONECTAR A POSTGRESQL ------- #
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "wildinfo"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            port=os.getenv("DB_PORT", "5432")
        )
        return conn
    except Exception as e:
        print(f"ERROR conectando a PostgreSQL: {e}")
        return None

# ------- INICIALIZAR BASE DE DATOS ------- #
def inicializar_db():
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            # Crear tabla si no existe
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS favoritos (
                id_favoritos SERIAL PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL,
                nombre_cientifico TEXT,
                especie TEXT,
                dieta TEXT,
                url_imagen VARCHAR(500),
                taxonomia TEXT,
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()
            cursor.close()
            print("DEBUG: ✅ Tabla 'favoritos' verificada/creada en PostgreSQL")
        except Exception as e:
            print(f"ERROR creando tabla: {e}")
        finally:
            conn.close()
    else:
        print("DEBUG: ⚠️ No se pudo conectar a PostgreSQL")

# Ejecutar inicialización al arrancar
inicializar_db()

# ------- ENDPOINT RAÍZ ------- #
@app.get("/")
async def root():
    return {"message": "Servidor WildInfo arriba", "Status": 200}

# ------- ENDPOINT PRINCIPAL (INTEGRACIÓN DE APIs) ------- #
@app.get("/animal/{name}")
async def buscar_animal(name: str):
    NINJAS_KEY = os.getenv("API_NINJAS_KEY")
    
    # 1. Diccionario de traducción para que API Ninjas entienda español
    traducciones = {
        "perro": "dog",
        "gato": "cat",
        "caballo": "horse",
        "conejo": "rabbit",
        "leon": "lion",
        "tigre": "tiger",
        "mosca": "fly",
        "sapo": "toad"
    }
    
    # Buscamos la traducción; si no existe, usamos el nombre original
    nombre_en = traducciones.get(name.lower(), name)

    # 2. URLs de las APIs
    url_ninjas = f"https://api.api-ninjas.com/v1/animals?name={nombre_en}"
    url_wiki = f"https://es.wikipedia.org/api/rest_v1/page/summary/{name}"
    
    if not NINJAS_KEY:
        raise HTTPException(status_code=500, detail="API Key no configurada")

    # 3. Headers (User-Agent actualizado para evitar bloqueos de Wikipedia)
    headers_ninjas = {"X-Api-Key": NINJAS_KEY}
    headers_wiki = {"User-Agent": "WildInfoApp/1.0 (contacto@wildinfo.com)"}

    async with httpx.AsyncClient() as client:
        try:
            # Petición a Ninjas
            resp_ninjas = await client.get(url_ninjas, headers=headers_ninjas)
            data_ninjas = resp_ninjas.json()

            # Petición a Wikipedia
            resp_wiki = await client.get(url_wiki, headers=headers_wiki)
            data_wiki = resp_wiki.json() if resp_wiki.status_code == 200 else {}

            if not data_ninjas and resp_wiki.status_code == 404:
                raise HTTPException(status_code=404, detail="Animal no encontrado")

            # 4. Lógica de filtrado para evitar resultados incorrectos
            info_tecnica = {}
            if data_ninjas:
                if name.lower() == "gato":
                    # Filtramos específicamente por el nombre científico del gato doméstico
                    info_tecnica = next(
                        (a for a in data_ninjas if a.get("taxonomy", {}).get("scientific_name") == "Felis catus"), 
                        data_ninjas[0]
                    )
                else:
                    info_tecnica = data_ninjas[0]
            
            # Obtener taxonomía como string para guardar
            taxonomia_str = str(info_tecnica.get("taxonomy", {})) if info_tecnica else "{}"
            
            return {
                "nombre": name.capitalize(),
                "nombre_ingles_usado": nombre_en,
                "cientifico": info_tecnica.get("taxonomy", {}).get("scientific_name", "No disponible"),
                "dieta": info_tecnica.get("characteristics", {}).get("diet", "No disponible"),
                "especie": info_tecnica.get("taxonomy", {}).get("order", "No disponible"),
                "taxonomia": taxonomia_str,
                "resumen_wiki": data_wiki.get("extract", "Sin resumen disponible"),
                "imagen": data_wiki.get("originalimage", {}).get("source", "Sin imagen"),
                "fuentes": {
                    "ninjas_ok": resp_ninjas.status_code == 200,
                    "wikipedia_ok": resp_wiki.status_code == 200
                }
            }

        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Error de conexión: {exc}")

# ------- ENDPOINT PARA GUARDAR EN FAVORITOS ------- #
@app.post("/favoritos/{name}")
async def guardar_favorito(name: str):
    # Primero obtenemos los datos del animal (reutilizando lógica)
    NINJAS_KEY = os.getenv("API_NINJAS_KEY")
    
    traducciones = {
        "perro": "dog", "gato": "cat", "caballo": "horse",
        "conejo": "rabbit", "leon": "lion", "tigre": "tiger",
        "mosca": "fly", "sapo": "toad"
    }
    
    nombre_en = traducciones.get(name.lower(), name)
    
    url_ninjas = f"https://api.api-ninjas.com/v1/animals?name={nombre_en}"
    url_wiki = f"https://es.wikipedia.org/api/rest_v1/page/summary/{name}"
    
    headers_ninjas = {"X-Api-Key": NINJAS_KEY}
    headers_wiki = {"User-Agent": "WildInfoApp/1.0"}
    
    async with httpx.AsyncClient() as client:
        try:
            # Obtener datos de las APIs
            resp_ninjas = await client.get(url_ninjas, headers=headers_ninjas)
            resp_wiki = await client.get(url_wiki, headers=headers_wiki)
            
            data_ninjas = resp_ninjas.json()
            data_wiki = resp_wiki.json() if resp_wiki.status_code == 200 else {}
            
            if not data_ninjas:
                raise HTTPException(status_code=404, detail="Animal no encontrado en API Ninjas")
            
            # Procesar datos (similar al endpoint GET)
            info_tecnica = data_ninjas[0]
            if name.lower() == "gato":
                info_tecnica = next(
                    (a for a in data_ninjas if a.get("taxonomy", {}).get("scientific_name") == "Felis catus"), 
                    data_ninjas[0]
                )
            
            # Guardar en PostgreSQL
            conn = get_db_connection()
            if not conn:
                raise HTTPException(status_code=503, detail="Base de datos no disponible")
            
            try:
                cursor = conn.cursor()
                
                # Verificar si ya existe
                cursor.execute("SELECT id_favoritos FROM favoritos WHERE nombre = %s", (name.capitalize(),))
                existe = cursor.fetchone()
                
                if existe:
                    return {
                        "status": "error",
                        "message": f"{name} ya está en favoritos"
                    }
                
                # Insertar nuevo favorito
                cursor.execute("""
                    INSERT INTO favoritos 
                    (nombre, nombre_cientifico, especie, dieta, url_imagen, taxonomia)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id_favoritos
                """, (
                    name.capitalize(),
                    info_tecnica.get("taxonomy", {}).get("scientific_name", "No disponible"),
                    info_tecnica.get("taxonomy", {}).get("order", "No disponible"),
                    info_tecnica.get("characteristics", {}).get("diet", "No disponible"),
                    data_wiki.get("originalimage", {}).get("source", ""),
                    str(info_tecnica.get("taxonomy", {}))
                ))
                
                conn.commit()
                favorito_id = cursor.fetchone()[0]
                
                return {
                    "status": "success",
                    "message": f"{name} guardado en favoritos",
                    "id": favorito_id
                }
                
            except Exception as e:
                conn.rollback()
                raise HTTPException(status_code=500, detail=f"Error al guardar: {str(e)}")
            finally:
                cursor.close()
                conn.close()
                
        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Error de conexión con APIs: {exc}")

# ------- ENDPOINT PARA LISTAR FAVORITOS ------- #
@app.get("/favoritos")
async def listar_favoritos():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM favoritos ORDER BY fecha_registro DESC")
        favoritos = cursor.fetchall()
        
        return list(favoritos)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al listar favoritos: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# ------- ENDPOINT PARA ELIMINAR FAVORITO ------- #
@app.delete("/favoritos/{favorito_id}")
async def eliminar_favorito(favorito_id: int):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")
    
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM favoritos WHERE id_favoritos = %s RETURNING nombre", (favorito_id,))
        eliminado = cursor.fetchone()
        conn.commit()
        
        if eliminado:
            return {
                "status": "success",
                "message": f"{eliminado[0]} eliminado de favoritos"
            }
        else:
            raise HTTPException(status_code=404, detail="Favorito no encontrado")
            
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al eliminar: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# ------- PUNTO DE ENTRADA ------- #
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
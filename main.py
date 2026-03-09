from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import time
import httpx
from dotenv import load_dotenv
import os

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

            # 4. Lógica de filtrado para evitar resultados incorrectos (como el lobo)
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
            
            return {
                "nombre": name.capitalize(),
                "nombre_ingles_usado": nombre_en,
                "cientifico": info_tecnica.get("taxonomy", {}).get("scientific_name", "No disponible"),
                "dieta": info_tecnica.get("characteristics", {}).get("diet", "No disponible"),
                "resumen_wiki": data_wiki.get("extract", "Sin resumen disponible"),
                "imagen": data_wiki.get("originalimage", {}).get("source", "Sin imagen"),
                "fuentes": {
                    "ninjas_ok": resp_ninjas.status_code == 200,
                    "wikipedia_ok": resp_wiki.status_code == 200
                }
            }

        except httpx.RequestError as exc:
            raise HTTPException(status_code=503, detail=f"Error de conexión: {exc}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
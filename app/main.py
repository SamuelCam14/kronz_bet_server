# RUTA: app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv
import os

# Importa los routers existentes y el nuevo
from .routers import games, boxscores
from .routers import live # *** NUEVO IMPORT ***

# Carga variables de entorno (si tienes un .env en la raíz de server_py)
# load_dotenv() # Descomenta si usas .env

app = FastAPI(title="NBA Scores API (Python)")

# Configuración de CORS
# Asegúrate que la URL de tu frontend React esté aquí
origins = [
    "http://localhost:5173", # Puerto por defecto de Vite/React
    "http://127.0.0.1:5173",
    # Añade la URL de producción si despliegas
    # "https://tu-dominio-frontend.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Permite todos los métodos (GET, POST, etc.)
    allow_headers=["*"], # Permite todos los headers
)

# Montar los routers con prefijos
app.include_router(games.router, prefix="/api/games", tags=["Games"])
app.include_router(boxscores.router, prefix="/api/boxscores", tags=["Boxscores"])
app.include_router(live.router, prefix="/api/live_scores", tags=["Live Scores"]) # *** MONTAR NUEVO ROUTER ***

@app.get("/", tags=["Root"])
async def read_root():
    """ Raíz de la API """
    return {"message": "Welcome to the NBA Scores Python API!"}

# Configuración para ejecutar con uvicorn directamente (opcional)
# if __name__ == "__main__":
#     port = int(os.getenv("PORT", 8000)) # Puerto 8000 por defecto
#     print(f"Starting Uvicorn server on http://0.0.0.0:{port}")
#     uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
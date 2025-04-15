# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv
import os

# Importa los routers
from .routers import games, boxscores

# Carga variables de entorno (si tienes un .env)
load_dotenv()

app = FastAPI(title="NBA Scores API (Python)")

# Configuración de CORS
# Asegúrate que la URL de tu frontend React esté aquí
origins = [
    "http://localhost:5173", # Puerto por defecto de Vite/React
    "http://127.0.0.1:5173",
    # Añade la URL de producción si despliegas
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

@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to the NBA Scores Python API!"}

# --- (Opcional) Para ejecutar con `python app/main.py` ---
# if __name__ == "__main__":
#     port = int(os.getenv("PORT", 8000)) # Usa puerto 8000 por defecto
#     uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
# --- Se recomienda usar `uvicorn app.main:app --reload --port 8000` desde la terminal ---
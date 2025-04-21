# RUTA: app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv
import os

# Importa los routers existentes y el nuevo
from .routers import games, boxscores, live
from .routers import predictions # *** NUEVO IMPORT ***

# Carga variables de entorno (si tienes un .env)
# load_dotenv()

app = FastAPI(title="NBA Scores API (Python)")

origins = [ "http://localhost:5173", "http://127.0.0.1:5173", 'https://kronzbet.netlify.app/' ] # Ajusta

app.add_middleware( CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"], )

# Montar los routers
app.include_router(games.router, prefix="/api/games", tags=["Games"])
app.include_router(boxscores.router, prefix="/api/boxscores", tags=["Boxscores"])
app.include_router(live.router, prefix="/api/live_scores", tags=["Live Scores"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["Predictions"]) # *** MONTAR NUEVO ROUTER ***

@app.get("/", tags=["Root"])
async def read_root(): return {"message": "Welcome to the NBA Scores Python API!"}

# if __name__ == "__main__":
#     port = int(os.getenv("PORT", 8000))
#     uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
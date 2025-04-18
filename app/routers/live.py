# RUTA: app/routers/live.py
from fastapi import APIRouter, HTTPException
from nba_api.live.nba.endpoints import scoreboard # Importa el scoreboard en vivo
import traceback
import json # Para logs detallados

router = APIRouter()

def transform_live_score_data(live_data):
    """Transforms data from the live scoreboard endpoint."""
    transformed_games = []
    # Verificar estructura inicial
    if not isinstance(live_data, dict) or 'scoreboard' not in live_data or not isinstance(live_data['scoreboard'], dict) or 'games' not in live_data['scoreboard']:
        print("[Live Transform] Invalid or missing live scoreboard data structure. Expected {'scoreboard': {'games': [...]}}")
        return transformed_games

    live_games = live_data['scoreboard']['games']
    if not isinstance(live_games, list):
        print("[Live Transform] 'games' key does not contain a list.")
        return transformed_games

    print(f"[Live Transform] Processing {len(live_games)} live games.")

    for game in live_games:
        try:
            # Verificar que 'game' sea un diccionario
            if not isinstance(game, dict):
                print(f"[Live Transform] Skipping item, not a dictionary: {type(game)}")
                continue

            # Extrae los datos clave del juego en vivo
            game_id = game.get('gameId')
            status_text = game.get('gameStatusText') # "Q1 9:34", "Halftime", "Final"
            period = game.get('period')
            game_clock = game.get('gameClock')

            home_team_data = game.get('homeTeam')
            away_team_data = game.get('awayTeam') # 'awayTeam' parece ser la clave correcta aquí

            # Validar datos críticos
            if not game_id or not isinstance(home_team_data, dict) or not isinstance(away_team_data, dict):
                print(f"[Live Transform] Skipping game due to missing critical data (gameId, homeTeam, awayTeam) for game: {game.get('gameEt', game_id)}")
                continue

            home_score = home_team_data.get('score')
            away_score = away_team_data.get('score')

            # Construye el objeto simplificado para el frontend
            transformed = {
                "id": game_id,
                # Convertir scores a int si no son None, sino None
                "home_team_score": int(home_score) if home_score is not None else None,
                "visitor_team_score": int(away_score) if away_score is not None else None,
                "status": status_text,
                "period": int(period) if period is not None else 0,
                "game_clock": game_clock
            }
            transformed_games.append(transformed)

        except Exception as e:
            print(f"[Live Transform] Error processing a live game (ID: {game.get('gameId', 'N/A')}): {e}")
            # Opcional: Imprime el juego problemático para depuración
            # try: print(json.dumps(game, indent=2))
            # except: pass
            traceback.print_exc()
            continue # Salta al siguiente juego si uno falla

    print(f"[Live Transform] Finished transforming {len(transformed_games)} live games.")
    return transformed_games


@router.get("/")
async def get_current_live_scores():
    """
    Fetches and returns simplified live score data for currently active games.
    """
    print("[API /live_scores] Request received for live data.")
    try:
        live_board = scoreboard.ScoreBoard()
        # get_dict() puede lanzar excepciones si la API falla
        live_data = live_board.get_dict()

        # --- Log para inspeccionar la estructura ---
        print("[API /live_scores] Raw Live Data Structure Sample (first 500 chars):")
        try: print(json.dumps(live_data, indent=2)[:500] + "...")
        except: print("Could not serialize raw live data for logging.")
        # --- Fin Log ---

        transformed_data = transform_live_score_data(live_data)
        return transformed_data

    except Exception as e:
        print(f"[API /live_scores] UNEXPECTED Error fetching live scores: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve live scores: {str(e)}")
# RUTA: app/routers/boxscores.py
from fastapi import APIRouter, HTTPException, Path
from nba_api.stats.endpoints import boxscoretraditionalv3
from ..utils.data_transformer import transform_boxscore_data # Importa el transformador
import traceback

router = APIRouter()

@router.get("/{game_id}")
async def get_boxscore_for_game(
    game_id: str = Path(..., description="The NBA.com Game ID")
):
    """
    Retrieves and transforms the box score for a specific NBA Game ID using V3 endpoint,
    handling the nested statistics structure.
    """
    print(f"[API /boxscores V3] Request received for Game ID: {game_id}")
    if not game_id or len(game_id) != 10:
         raise HTTPException(status_code=400, detail="Invalid Game ID format.")

    try:
        boxscore = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=game_id)
        boxscore_data = boxscore.get_dict()

        print(f"[API /boxscores V3] Raw response keys: {boxscore_data.keys() if boxscore_data else 'None'}")

        if not boxscore_data or 'boxScoreTraditional' not in boxscore_data:
             print("[API /boxscores V3] Key 'boxScoreTraditional' not found.")
             return []

        boxscore_traditional_data = boxscore_data['boxScoreTraditional']
        print(f"[API /boxscores V3] Keys within 'boxScoreTraditional': {boxscore_traditional_data.keys() if isinstance(boxscore_traditional_data, dict) else 'Not a dict'}")

        home_team_data = boxscore_traditional_data.get('homeTeam')
        away_team_data = boxscore_traditional_data.get('awayTeam')

        combined_players_list = [] # Lista de diccionarios de jugadores (con stats anidadas)
        # --- *** NUEVO: Almacenar info del equipo para pasarla al transformador *** ---
        players_with_team_info = [] # Lista de tuplas: (player_dict, team_id, team_tricode)

        if isinstance(home_team_data, dict) and 'players' in home_team_data and isinstance(home_team_data['players'], list):
            home_players = home_team_data['players']
            home_team_id = home_team_data.get('teamId') # Obtener del objeto equipo
            home_team_tricode = home_team_data.get('teamTricode') # Obtener del objeto equipo
            print(f"[API /boxscores V3] Found {len(home_players)} players for home team {home_team_tricode} ({home_team_id}).")
            for player in home_players:
                players_with_team_info.append( (player, home_team_id, home_team_tricode) )
        else:
             print("[API /boxscores V3] 'players' key not found or invalid in 'homeTeam'.")

        if isinstance(away_team_data, dict) and 'players' in away_team_data and isinstance(away_team_data['players'], list):
            away_players = away_team_data['players']
            away_team_id = away_team_data.get('teamId')
            away_team_tricode = away_team_data.get('teamTricode')
            print(f"[API /boxscores V3] Found {len(away_players)} players for away team {away_team_tricode} ({away_team_id}).")
            for player in away_players:
                players_with_team_info.append( (player, away_team_id, away_team_tricode) )
        else:
             print("[API /boxscores V3] 'players' key not found or invalid in 'awayTeam'.")

        if not players_with_team_info:
            print("[API /boxscores V3] No player data found in either team object.")
            return []

        # --- OBTENER CABECERAS (del diccionario anidado 'statistics') Y RECONSTRUIR rowSet ---
        # Asumimos que 'statistics' existe en el primer jugador y tiene las claves de stats
        first_player_dict, _, _ = players_with_team_info[0]
        stats_dict = first_player_dict.get('statistics', {})
        stats_headers_original = list(stats_dict.keys()) # Cabeceras de las stats
        # Cabeceras principales (fuera de statistics)
        main_headers_original = list(first_player_dict.keys())
        # Combinar headers para el transformador (asegurándose de que 'statistics' no esté)
        all_expected_headers = [h for h in main_headers_original if h != 'statistics'] + stats_headers_original
        headers_lower = [h.lower() for h in all_expected_headers]

        # Reconstruir la lista de listas APLANANDO las stats
        raw_stats_as_list = []
        for player_dict, team_id, team_tricode in players_with_team_info:
            player_stats = player_dict.get('statistics', {})
            row = []
            # Añadir valores principales
            for header in main_headers_original:
                 if header == 'statistics': continue # Saltar el diccionario anidado
                 row.append(player_dict.get(header, None))
            # Añadir valores de estadísticas
            for stats_header in stats_headers_original:
                row.append(player_stats.get(stats_header, None))

            # *** Añadir team_id y team_tricode explícitamente para el transformador ***
            # Esto es un HACK porque no están como cabeceras, pero el transformador los necesita
            row.append(team_id)
            row.append(team_tricode)
            raw_stats_as_list.append(row)

        # Ajustar headers_lower para incluir los añadidos manualmente
        headers_lower_with_team = headers_lower + ['teamid', 'teamtricode']

        print(f"[API /boxscores V3] Reconstructed playerStats headers (lowercase, with team info): {headers_lower_with_team}")
        print(f"[API /boxscores V3] First row of reconstructed raw PlayerStats: {raw_stats_as_list[0] if raw_stats_as_list else 'Empty'}")

        # --- Llamada a la función transformadora (pasando cabeceras ajustadas) ---
        transformed_stats = transform_boxscore_data(raw_stats_as_list, headers_lower_with_team) # Pasamos las cabeceras completas

        print(f"[API /boxscores V3] Transformed {len(transformed_stats)} player stats for Game ID {game_id}")
        return transformed_stats

    except Exception as e:
        print(f"[API /boxscores V3] UNEXPECTED Error fetching box score for Game ID {game_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve V3 box score: {str(e)}")
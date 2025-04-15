# RUTA: app/routers/games.py
from fastapi import APIRouter, HTTPException, Query, Path
from datetime import datetime
import pytz # Necesario para zonas horarias
from nba_api.stats.endpoints import scoreboardv2
import traceback # Para imprimir stack traces detallados

router = APIRouter()

# Mapeo simple ID -> Abreviatura (podría ir a un archivo config si crece)
TEAM_ID_TO_ABBR = {
    1610612737: "ATL", 1610612738: "BOS", 1610612751: "BKN", 1610612766: "CHA",
    1610612741: "CHI", 1610612739: "CLE", 1610612742: "DAL", 1610612743: "DEN",
    1610612765: "DET", 1610612744: "GSW", 1610612745: "HOU", 1610612754: "IND",
    1610612746: "LAC", 1610612747: "LAL", 1610612763: "MEM", 1610612748: "MIA",
    1610612749: "MIL", 1610612750: "MIN", 1610612740: "NOP", 1610612752: "NYK",
    1610612760: "OKC", 1610612753: "ORL", 1610612755: "PHI", 1610612756: "PHX",
    1610612757: "POR", 1610612758: "SAC", 1610612759: "SAS", 1610612761: "TOR",
    1610612762: "UTA", 1610612764: "WAS",
}

# --- FUNCIÓN parse_nba_datetime_to_utc (CON INDENTACIÓN CORREGIDA) ---
def parse_nba_datetime_to_utc(game_date_est_str, game_status_text, status_id):
    """
    Intenta parsear la fecha/hora EST/EDT y convertirla a ISO 8601 UTC.
    Usa la hora del status_text si el juego está agendado (status_id=1).
    DEVUELVE None si el juego está finalizado (status_id=3) o el parseo falla gravemente.
    """
    print(f"--- Parsing DateTime ---")
    print(f"Input: date_est='{game_date_est_str}', status_text='{game_status_text}', status_id={status_id}")

    if status_id == 3:
        print("Game is Final (status_id=3). Returning None for datetime.")
        print(f"--- End Parsing DateTime --- Returning: None")
        return None

    datetime_utc_iso = None
    game_date_str = game_date_est_str.split('T')[0] # "YYYY-MM-DD"
    game_time_str = game_status_text.strip()

    should_parse_time = (
        status_id == 1 and
        ('PM' in game_time_str.upper() or 'AM' in game_time_str.upper()) and
        'TBD' not in game_time_str.upper() and
        'PPD' not in game_time_str.upper()
    )
    print(f"Condition check: Should parse time? {should_parse_time}")

    if should_parse_time:
        try:
            time_part = game_time_str.upper().replace(' ET', '').strip()
            full_datetime_str_est = f"{game_date_str} {time_part}"
            print(f"Attempting to parse: '{full_datetime_str_est}' with format '%Y-%m-%d %I:%M %p'")
            dt_naive_est = datetime.strptime(full_datetime_str_est, '%Y-%m-%d %I:%M %p')
            eastern = pytz.timezone('America/New_York')
            dt_aware_est = eastern.localize(dt_naive_est)
            dt_utc = dt_aware_est.astimezone(pytz.utc)
            datetime_utc_iso = dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
            print(f"Successfully parsed and converted to UTC: {datetime_utc_iso}")
        except ValueError as parse_err:
            # --- *** BLOQUE CORREGIDO CON INDENTACIÓN *** ---
            print(f"!!! ValueError during strptime: {parse_err}. String was: '{full_datetime_str_est}'")
            # Intenta el fallback DENTRO del except ValueError
            try:
                base_date_est = datetime.strptime(game_date_str, '%Y-%m-%d')
                eastern = pytz.timezone('America/New_York')
                dt_aware_est = eastern.localize(base_date_est)
                dt_utc = dt_aware_est.astimezone(pytz.utc)
                datetime_utc_iso = dt_utc.strftime('%Y-%m-%dT00:00:00Z')
                print(f"WARN: Using fallback UTC midnight due to time parsing error.")
            except Exception as fallback_err:
                 print(f"!!! Error generating fallback datetime after parse error: {fallback_err}")
                 datetime_utc_iso = None # Falla el fallback también
            # --- *** FIN BLOQUE CORREGIDO *** ---
        except Exception as other_err:
            print(f"!!! Unexpected error during time parsing/conversion: {other_err}")
            datetime_utc_iso = None

    # Fallback si la condición inicial no se cumplió o si hubo error antes
    # Y datetime_utc_iso sigue siendo None
    if datetime_utc_iso is None:
         # Solo muestra warning si no fue un error de parseo previo
        if not (should_parse_time and isinstance(locals().get('parse_err'), ValueError)):
             if status_id != 2: # No mostrar warning para juegos en progreso (status 2)
                 print(f"WARN: Condition to parse time not met or previous error. Using fallback UTC midnight for status '{game_status_text}'")
        try:
            base_date_est = datetime.strptime(game_date_str, '%Y-%m-%d')
            eastern = pytz.timezone('America/New_York')
            dt_aware_est = eastern.localize(base_date_est)
            dt_utc = dt_aware_est.astimezone(pytz.utc)
            datetime_utc_iso = dt_utc.strftime('%Y-%m-%dT00:00:00Z')
        except Exception as fallback_err:
             print(f"!!! Error generating final fallback datetime: {fallback_err}")
             datetime_utc_iso = None # Falla total

    print(f"--- End Parsing DateTime --- Returning: {datetime_utc_iso}")
    return datetime_utc_iso

# --- Función auxiliar para procesar datos del scoreboard ---
def process_scoreboard_data(date):
    """ Función auxiliar para procesar scoreboard y devolver mapas/listas útiles """
    print(f"[Process Scoreboard] Processing data for date: {date}")
    try:
        scoreboard = scoreboardv2.ScoreboardV2(game_date=date, league_id='00')
        scoreboard_data = scoreboard.get_dict()
    except Exception as api_err:
        print(f"[Process Scoreboard] Error calling ScoreboardV2 API: {api_err}")
        return None, None, None, None # Devuelve todos None si la API falla

    if not scoreboard_data or 'resultSets' not in scoreboard_data:
        print(f"[Process Scoreboard] No resultSets found for {date}")
        return None, None, None, None

    # Extraer GameHeader
    game_header_set = next((rs for rs in scoreboard_data['resultSets'] if rs['name'] == 'GameHeader'), None)
    if not game_header_set or 'rowSet' not in game_header_set or not game_header_set['rowSet']:
        print(f"[Process Scoreboard] 'GameHeader' not found or empty for {date}.")
        return None, None, None, None
    gh_headers = [h.lower() for h in game_header_set['headers']]
    gh_rows = game_header_set['rowSet']

    # Extraer LineScore
    line_score_set = next((rs for rs in scoreboard_data['resultSets'] if rs['name'] == 'LineScore'), None)
    scores_map = {}
    quarter_scores_map = {}
    if line_score_set and 'rowSet' in line_score_set and line_score_set['rowSet']:
        ls_headers = [h.lower() for h in line_score_set['headers']]
        ls_rows = line_score_set['rowSet']
        try:
            idx_ls_game_id=ls_headers.index('game_id'); idx_ls_team_id=ls_headers.index('team_id'); idx_ls_pts=ls_headers.index('pts')
            qtr_indices = []
            for i in range(1, 5): qtr_indices.append(ls_headers.index(f'pts_qtr{i}') if f'pts_qtr{i}' in ls_headers else -1)
            for i in range(1, 11): qtr_indices.append(ls_headers.index(f'pts_ot{i}') if f'pts_ot{i}' in ls_headers else -1)

            for row in ls_rows:
                game_id=row[idx_ls_game_id]; team_id=row[idx_ls_team_id]
                total_pts = row[idx_ls_pts] if row[idx_ls_pts] is not None else 0; scores_map[(game_id, team_id)] = total_pts
                q_scores = [int(row[idx]) if idx != -1 and row[idx] is not None else None for idx in qtr_indices]
                quarter_scores_map[(game_id, team_id)] = [s for s in q_scores if s is not None]
        except ValueError as e: print(f"!!! Error processing LineScore headers: {e}")
    else: print("[Process Scoreboard] 'LineScore' not found or empty.")

    return gh_rows, gh_headers, scores_map, quarter_scores_map

# --- Endpoint GET /api/games/ ---
@router.get("/")
async def get_games_for_date(date: str = Query(..., pattern="^\d{4}-\d{2}-\d{2}$")):
    print(f"[API /games] Request received for date: {date}")
    try:
        gh_rows, gh_headers, scores_map, quarter_scores_map = process_scoreboard_data(date)
        if gh_rows is None: return [] # Retorna vacío si el helper falló
        try:
            idx_gh_game_date_est=gh_headers.index('game_date_est'); idx_gh_game_id=gh_headers.index('game_id'); idx_gh_game_status_id=gh_headers.index('game_status_id'); idx_gh_game_status_text=gh_headers.index('game_status_text'); idx_gh_home_team_id=gh_headers.index('home_team_id'); idx_gh_visitor_team_id=gh_headers.index('visitor_team_id'); idx_gh_period=gh_headers.index('period') if 'period' in gh_headers else -1; idx_gh_home_team_name=gh_headers.index('home_team_name') if 'home_team_name' in gh_headers else -1; idx_gh_visitor_team_name=gh_headers.index('visitor_team_name') if 'visitor_team_name' in gh_headers else -1
        except ValueError as e: raise HTTPException(status_code=500, detail=f"GameHeader structure mismatch: {e}")

        transformed_games = []
        for gh_row in gh_rows:
            game_id=gh_row[idx_gh_game_id]; home_team_id=gh_row[idx_gh_home_team_id]; visitor_team_id=gh_row[idx_gh_visitor_team_id]; status_id=gh_row[idx_gh_game_status_id]; status_text=gh_row[idx_gh_game_status_text]; game_date_est_str=gh_row[idx_gh_game_date_est]
            home_score = scores_map.get((game_id, home_team_id), 0); visitor_score = scores_map.get((game_id, visitor_team_id), 0)
            period = gh_row[idx_gh_period] if idx_gh_period != -1 else 0
            home_abbr = TEAM_ID_TO_ABBR.get(home_team_id, "UNK"); visitor_abbr = TEAM_ID_TO_ABBR.get(visitor_team_id, "UNK")
            home_name = gh_row[idx_gh_home_team_name] if idx_gh_home_team_name != -1 else home_abbr; visitor_name = gh_row[idx_gh_visitor_team_name] if idx_gh_visitor_team_name != -1 else visitor_abbr
            datetime_utc_iso = parse_nba_datetime_to_utc(game_date_est_str, status_text, status_id)
            home_q_scores = quarter_scores_map.get((game_id, home_team_id), []); visitor_q_scores = quarter_scores_map.get((game_id, visitor_team_id), [])
            max_periods = max(len(home_q_scores), len(visitor_q_scores)); period_scores_structured = []
            for i in range(max_periods): period_label = f"Q{i+1}" if i < 4 else f"OT{i-3}"; h_score = home_q_scores[i] if i < len(home_q_scores) else 0; v_score = visitor_q_scores[i] if i < len(visitor_q_scores) else 0; period_scores_structured.append({"period": i + 1, "period_name": period_label, "home_score": h_score, "visitor_score": v_score})
            try: home_score_num = int(home_score); visitor_score_num = int(visitor_score)
            except ValueError: home_score_num = 0; visitor_score_num = 0
            transformed_game = { "id": game_id, "date": game_date_est_str, "datetime": datetime_utc_iso, "home_team_score": home_score_num, "visitor_team_score": visitor_score_num, "period": period, "status": status_text, "time": "", "home_team": {"id": home_team_id, "abbreviation": home_abbr, "full_name": home_name, "name": home_name.split(' ')[-1] if home_name and ' ' in home_name else home_abbr,}, "visitor_team": {"id": visitor_team_id, "abbreviation": visitor_abbr, "full_name": visitor_name, "name": visitor_name.split(' ')[-1] if visitor_name and ' ' in visitor_name else visitor_abbr,}, "period_scores": period_scores_structured }
            transformed_games.append(transformed_game)

        transformed_games.sort(key=lambda g: g['datetime'] or '9999-12-31T23:59:59Z')
        print(f"[API /games] Returning {len(transformed_games)} combined & transformed games for {date}")
        return transformed_games
    except Exception as e: print(f"[API /games] UNEXPECTED Error fetching games for date {date}: {e}"); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"Failed to retrieve games: {str(e)}")

# --- Endpoint GET /api/games/{game_id} (CON FECHA REQUERIDA) ---
@router.get("/{game_id}", response_model=dict)
async def get_game_details(
    game_id: str = Path(..., pattern="^\d{10}$"),
    date: str = Query(..., pattern="^\d{4}-\d{2}-\d{2}$") # Fecha requerida
):
    print(f"[API /games/{game_id}] Request received for date: {date}")
    try:
        gh_rows, gh_headers, scores_map, quarter_scores_map = process_scoreboard_data(date)
        if gh_rows is None: raise HTTPException(status_code=404, detail=f"Game data not found for date {date}.")

        target_row = None
        try: idx_gh_game_id = gh_headers.index('game_id')
        except ValueError: raise HTTPException(status_code=500, detail="GameHeader structure mismatch: missing game_id")
        for row in gh_rows:
            if row[idx_gh_game_id] == game_id: target_row = row; break
        if target_row is None: raise HTTPException(status_code=404, detail=f"Game ID {game_id} not found for date {date}.")

        gh_row = target_row
        try: # Índices GameHeader
            idx_gh_game_date_est=gh_headers.index('game_date_est'); idx_gh_game_status_id=gh_headers.index('game_status_id'); idx_gh_game_status_text=gh_headers.index('game_status_text'); idx_gh_home_team_id=gh_headers.index('home_team_id'); idx_gh_visitor_team_id=gh_headers.index('visitor_team_id'); idx_gh_period=gh_headers.index('period') if 'period' in gh_headers else -1; idx_gh_home_team_name=gh_headers.index('home_team_name') if 'home_team_name' in gh_headers else -1; idx_gh_visitor_team_name=gh_headers.index('visitor_team_name') if 'visitor_team_name' in gh_headers else -1
        except ValueError as e: raise HTTPException(status_code=500, detail=f"GameHeader structure mismatch: {e}")
        home_team_id=gh_row[idx_gh_home_team_id]; visitor_team_id=gh_row[idx_gh_visitor_team_id]; status_id=gh_row[idx_gh_game_status_id]; status_text=gh_row[idx_gh_game_status_text]; game_date_est_str=gh_row[idx_gh_game_date_est]
        home_score = scores_map.get((game_id, home_team_id), 0); visitor_score = scores_map.get((game_id, visitor_team_id), 0)
        period = gh_row[idx_gh_period] if idx_gh_period != -1 else 0
        home_abbr = TEAM_ID_TO_ABBR.get(home_team_id, "UNK"); visitor_abbr = TEAM_ID_TO_ABBR.get(visitor_team_id, "UNK")
        home_name = gh_row[idx_gh_home_team_name] if idx_gh_home_team_name != -1 else home_abbr; visitor_name = gh_row[idx_gh_visitor_team_name] if idx_gh_visitor_team_name != -1 else visitor_abbr
        datetime_utc_iso = parse_nba_datetime_to_utc(game_date_est_str, status_text, status_id)
        home_q_scores = quarter_scores_map.get((game_id, home_team_id), []); visitor_q_scores = quarter_scores_map.get((game_id, visitor_team_id), [])
        max_periods = max(len(home_q_scores), len(visitor_q_scores)); period_scores_structured = []
        for i in range(max_periods): period_label = f"Q{i+1}" if i < 4 else f"OT{i-3}"; h_score = home_q_scores[i] if i < len(home_q_scores) else 0; v_score = visitor_q_scores[i] if i < len(visitor_q_scores) else 0; period_scores_structured.append({"period": i + 1, "period_name": period_label, "home_score": h_score, "visitor_score": v_score})
        try: home_score_num = int(home_score); visitor_score_num = int(visitor_score)
        except ValueError: home_score_num = 0; visitor_score_num = 0
        single_game_details = { "id": game_id, "date": game_date_est_str, "datetime": datetime_utc_iso, "home_team_score": home_score_num, "visitor_team_score": visitor_score_num, "period": period, "status": status_text, "time": "", "home_team": {"id": home_team_id, "abbreviation": home_abbr, "full_name": home_name, "name": home_name.split(' ')[-1] if home_name and ' ' in home_name else home_abbr,}, "visitor_team": {"id": visitor_team_id, "abbreviation": visitor_abbr, "full_name": visitor_name, "name": visitor_name.split(' ')[-1] if visitor_name and ' ' in visitor_name else visitor_abbr,}, "period_scores": period_scores_structured }

        print(f"[API /games/{game_id}] Returning details for game on date {date}.")
        return single_game_details
    except HTTPException as http_exc: raise http_exc
    except Exception as e: print(f"[API /games/{game_id}] UNEXPECTED Error fetching game details: {e}"); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"Failed to retrieve game details: {str(e)}")
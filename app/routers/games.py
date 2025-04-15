# RUTA: app/routers/games.py
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
import pytz
from nba_api.stats.endpoints import scoreboardv2
import traceback

router = APIRouter()

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

def parse_nba_datetime_to_utc(game_date_est_str, game_status_text, status_id):
    # ... (Función sin cambios desde la última versión - devuelve None si status_id == 3) ...
    print(f"--- Parsing DateTime ---")
    print(f"Input: date_est='{game_date_est_str}', status_text='{game_status_text}', status_id={status_id}")
    if status_id == 3: print("Game is Final (status_id=3). Returning None for datetime."); print(f"--- End Parsing DateTime --- Returning: None"); return None
    datetime_utc_iso = None; game_date_str = game_date_est_str.split('T')[0]; game_time_str = game_status_text.strip()
    should_parse_time = ( status_id == 1 and ('PM' in game_time_str.upper() or 'AM' in game_time_str.upper()) and 'TBD' not in game_time_str.upper() and 'PPD' not in game_time_str.upper() )
    print(f"Condition check: Should parse time? {should_parse_time}")
    if should_parse_time:
        try:
            time_part = game_time_str.upper().replace(' ET', '').strip(); full_datetime_str_est = f"{game_date_str} {time_part}"
            print(f"Attempting to parse: '{full_datetime_str_est}' with format '%Y-%m-%d %I:%M %p'")
            dt_naive_est = datetime.strptime(full_datetime_str_est, '%Y-%m-%d %I:%M %p'); eastern = pytz.timezone('America/New_York')
            dt_aware_est = eastern.localize(dt_naive_est); dt_utc = dt_aware_est.astimezone(pytz.utc)
            datetime_utc_iso = dt_utc.strftime('%Y-%m-%dT%H:%M:%SZ'); print(f"Successfully parsed and converted to UTC: {datetime_utc_iso}")
        except ValueError as parse_err:
            print(f"!!! ValueError during strptime: {parse_err}. String was: '{full_datetime_str_est}'")
            try: base_date_est = datetime.strptime(game_date_str, '%Y-%m-%d'); eastern = pytz.timezone('America/New_York'); dt_aware_est = eastern.localize(base_date_est); dt_utc = dt_aware_est.astimezone(pytz.utc); datetime_utc_iso = dt_utc.strftime('%Y-%m-%dT00:00:00Z'); print(f"WARN: Using fallback UTC midnight due to time parsing error.")
            except Exception as fallback_err: print(f"!!! Error generating fallback datetime after parse error: {fallback_err}"); datetime_utc_iso = None
        except Exception as other_err: print(f"!!! Unexpected error during time parsing/conversion: {other_err}"); datetime_utc_iso = None
    if datetime_utc_iso is None:
        if status_id != 2: print(f"WARN: Condition to parse time not met or previous error. Using fallback UTC midnight for status '{game_status_text}'")
        try: base_date_est = datetime.strptime(game_date_str, '%Y-%m-%d'); eastern = pytz.timezone('America/New_York'); dt_aware_est = eastern.localize(base_date_est); dt_utc = dt_aware_est.astimezone(pytz.utc); datetime_utc_iso = dt_utc.strftime('%Y-%m-%dT00:00:00Z')
        except Exception as fallback_err: print(f"!!! Error generating final fallback datetime: {fallback_err}"); datetime_utc_iso = None
    print(f"--- End Parsing DateTime --- Returning: {datetime_utc_iso}")
    return datetime_utc_iso

@router.get("/")
async def get_games_for_date(
    date: str = Query(..., description="Date in YYYY-MM-DD format", pattern="^\d{4}-\d{2}-\d{2}$")
):
    """
    Retrieves games for a date, combining GameHeader and LineScore data,
    including quarter scores.
    """
    print(f"[API /games] Request received for date: {date}")
    try:
        scoreboard = scoreboardv2.ScoreboardV2(game_date=date, league_id='00')
        scoreboard_data = scoreboard.get_dict()

        if not scoreboard_data or 'resultSets' not in scoreboard_data: return []

        # --- Extraer GameHeader ---
        game_header_set = next((rs for rs in scoreboard_data['resultSets'] if rs['name'] == 'GameHeader'), None)
        if not game_header_set or 'rowSet' not in game_header_set or not game_header_set['rowSet']: return []
        gh_headers = [h.lower() for h in game_header_set['headers']]
        gh_rows = game_header_set['rowSet']
        print(f"[API /games] Found {len(gh_rows)} rows in GameHeader.")
        try: # Índices GameHeader
            idx_gh_game_date_est=gh_headers.index('game_date_est'); idx_gh_game_id=gh_headers.index('game_id')
            idx_gh_game_status_id=gh_headers.index('game_status_id'); idx_gh_game_status_text=gh_headers.index('game_status_text')
            idx_gh_home_team_id=gh_headers.index('home_team_id'); idx_gh_visitor_team_id=gh_headers.index('visitor_team_id')
            idx_gh_period=gh_headers.index('period') if 'period' in gh_headers else -1
            idx_gh_home_team_name=gh_headers.index('home_team_name') if 'home_team_name' in gh_headers else -1
            idx_gh_visitor_team_name=gh_headers.index('visitor_team_name') if 'visitor_team_name' in gh_headers else -1
        except ValueError as e: raise HTTPException(status_code=500, detail=f"GameHeader structure mismatch: {e}")

        # --- Extraer LineScore y crear mapas de scores TOTALES y POR CUARTO ---
        line_score_set = next((rs for rs in scoreboard_data['resultSets'] if rs['name'] == 'LineScore'), None)
        scores_map = {} # { (game_id, team_id): total_pts }
        quarter_scores_map = {} # { (game_id, team_id): [q1, q2, q3, q4, ot1,...] }
        if line_score_set and 'rowSet' in line_score_set and line_score_set['rowSet']:
            ls_headers = [h.lower() for h in line_score_set['headers']]
            ls_rows = line_score_set['rowSet']
            print(f"[API /games] Found {len(ls_rows)} rows in LineScore.")
            try: # Índices LineScore
                idx_ls_game_id=ls_headers.index('game_id'); idx_ls_team_id=ls_headers.index('team_id')
                idx_ls_pts=ls_headers.index('pts')
                # Índices de Cuartos/OT (manejar si no existen)
                qtr_indices = []
                for i in range(1, 5): # Q1 a Q4
                    key = f'pts_qtr{i}'
                    qtr_indices.append(ls_headers.index(key) if key in ls_headers else -1)
                for i in range(1, 11): # OT1 a OT10
                    key = f'pts_ot{i}'
                    qtr_indices.append(ls_headers.index(key) if key in ls_headers else -1)

                # Poblar los mapas
                for row in ls_rows:
                    game_id=row[idx_ls_game_id]; team_id=row[idx_ls_team_id]
                    # Mapa de total
                    total_pts = row[idx_ls_pts] if row[idx_ls_pts] is not None else 0
                    scores_map[(game_id, team_id)] = total_pts
                    # Mapa de cuartos
                    q_scores = []
                    for idx in qtr_indices:
                        if idx != -1:
                            q_score = row[idx] # Puede ser None si no se jugó OT
                            q_scores.append(int(q_score) if q_score is not None else None)
                        else:
                            q_scores.append(None) # Añade None si el header no existía
                    # Guarda solo los scores que no son None al final (maneja OTs no jugados)
                    # Filtramos None al final para saber cuántos periodos hubo realmente
                    quarter_scores_map[(game_id, team_id)] = [s for s in q_scores if s is not None]

                print(f"[API /games] Populated scores_map ({len(scores_map)}) and quarter_scores_map ({len(quarter_scores_map)})")
            except ValueError as e:
                print(f"!!! Error: Missing required header in LineScore - {e}. Headers: {ls_headers}")
        else:
             print("[API /games] 'LineScore' resultSet not found or empty. Scores will be 0/empty.")

        # --- Combinar y Transformar ---
        transformed_games = []
        for gh_row in gh_rows:
            game_id=gh_row[idx_gh_game_id]; home_team_id=gh_row[idx_gh_home_team_id]
            visitor_team_id=gh_row[idx_gh_visitor_team_id]; status_id=gh_row[idx_gh_game_status_id]
            status_text=gh_row[idx_gh_game_status_text]; game_date_est_str=gh_row[idx_gh_game_date_est]
            home_score = scores_map.get((game_id, home_team_id), 0)
            visitor_score = scores_map.get((game_id, visitor_team_id), 0)
            period = gh_row[idx_gh_period] if idx_gh_period != -1 else 0
            home_abbr = TEAM_ID_TO_ABBR.get(home_team_id, "UNK"); visitor_abbr = TEAM_ID_TO_ABBR.get(visitor_team_id, "UNK")
            home_name = gh_row[idx_gh_home_team_name] if idx_gh_home_team_name != -1 else home_abbr
            visitor_name = gh_row[idx_gh_visitor_team_name] if idx_gh_visitor_team_name != -1 else visitor_abbr
            datetime_utc_iso = parse_nba_datetime_to_utc(game_date_est_str, status_text, status_id)

            # *** NUEVO: Obtener y estructurar scores por periodo ***
            home_q_scores = quarter_scores_map.get((game_id, home_team_id), [])
            visitor_q_scores = quarter_scores_map.get((game_id, visitor_team_id), [])
            # Asegurarse que ambas listas tengan la misma longitud (la máxima encontrada)
            max_periods = max(len(home_q_scores), len(visitor_q_scores))
            period_scores_structured = []
            for i in range(max_periods):
                period_label = f"Q{i+1}" if i < 4 else f"OT{i-3}"
                h_score = home_q_scores[i] if i < len(home_q_scores) else 0 # Default 0 si falta
                v_score = visitor_q_scores[i] if i < len(visitor_q_scores) else 0
                period_scores_structured.append({
                    "period": i + 1,
                    "period_name": period_label,
                    "home_score": h_score,
                    "visitor_score": v_score
                })
            # *** FIN NUEVO ***

            try: # Asegurar scores numéricos
                home_score_num = int(home_score); visitor_score_num = int(visitor_score)
            except ValueError: home_score_num = 0; visitor_score_num = 0

            transformed_game = {
                "id": game_id, "date": game_date_est_str, "datetime": datetime_utc_iso,
                "home_team_score": home_score_num, "visitor_team_score": visitor_score_num,
                "period": period, "status": status_text, "time": "",
                "home_team": {"id": home_team_id, "abbreviation": home_abbr, "full_name": home_name, "name": home_name.split(' ')[-1] if home_name and ' ' in home_name else home_abbr,},
                "visitor_team": {"id": visitor_team_id, "abbreviation": visitor_abbr, "full_name": visitor_name, "name": visitor_name.split(' ')[-1] if visitor_name and ' ' in visitor_name else visitor_abbr,},
                "period_scores": period_scores_structured # *** Añade la nueva estructura ***
            }
            transformed_games.append(transformed_game)

        transformed_games.sort(key=lambda g: g['datetime'] or '9999-12-31T23:59:59Z')

        print(f"[API /games] Returning {len(transformed_games)} combined & transformed games for {date}")
        return transformed_games

    except Exception as e:
        print(f"[API /games] UNEXPECTED Error fetching games for date {date}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to retrieve games: {str(e)}")
# RUTA: app/routers/predictions.py
from fastapi import APIRouter, HTTPException, Query
from nba_api.stats.endpoints import leaguestandingsv3
import traceback
import time
import math
# *** IMPORTAR DATETIME ***
from datetime import datetime # <--- ¡Faltaba esta línea!

router = APIRouter()

# --- Pesos y Cache (sin cambios) ---
WEIGHTS = { 'overall_wpct': 0.10, 'location_wpct': 0.15, 'last10_wpct': 0.15, 'overall_diff': 0.30, 'location_diff': 0.15, 'last10_diff': 0.15 }
standings_cache = { "data": None, "timestamp": 0, "ttl_seconds": 60 * 15 }

async def get_standings_data():
    """ Obtiene datos de standings, usando caché simple. """
    now = time.time()
    if standings_cache["data"] and (now - standings_cache["timestamp"] < standings_cache["ttl_seconds"]):
        print("[Standings Cache] Using cached data.")
        return standings_cache["data"]
    print("[Standings Cache] Fetching new standings data...")
    try:
        # Ahora 'datetime' está definido
        current_year = datetime.now().year
        current_month = datetime.now().month
        season_year_str = f"{current_year-1}-{str(current_year)[-2:]}" if current_month < 9 else f"{current_year}-{str(current_year+1)[-2:]}"
        print(f"[Standings Cache] Using season: {season_year_str}")

        standings = leaguestandingsv3.LeagueStandingsV3(league_id='00', season=season_year_str)
        standings_data = standings.get_dict()
        if not standings_data or 'resultSets' not in standings_data or not standings_data['resultSets']:
            print("!!! Error: Could not retrieve valid standings data from NBA API."); return None
        standings_set = standings_data['resultSets'][0]
        headers = [h.lower() for h in standings_set['headers']]
        rows = standings_set['rowSet']
        standings_cache["data"] = {"headers": headers, "rows": rows}
        standings_cache["timestamp"] = now
        print(f"[Standings Cache] Data fetched and cached. Headers: {headers}")
        return standings_cache["data"]
    except Exception as e: print(f"!!! Exception fetching standings: {e}"); traceback.print_exc(); return None

# --- Función de Normalización (sin cambios) ---
def normalize_point_diff(diff, min_diff=-15.0, max_diff=15.0):
    if diff is None: return 0.5
    try: diff_float = float(diff); clamped_diff = max(min_diff, min(max_diff, diff_float)); normalized = (clamped_diff - min_diff) / (max_diff - min_diff); return normalized
    except (ValueError, TypeError): return 0.5

# --- Función de Cálculo de Probabilidad (sin cambios) ---
def calculate_win_probability(home_stats, visitor_stats):
    if not home_stats or not visitor_stats: return None
    print(f"[Calculator] Home Stats Input: {home_stats}")
    print(f"[Calculator] Visitor Stats Input: {visitor_stats}")
    try:
        def get_win_pct(stat_value):
            if isinstance(stat_value, (int, float)): return float(stat_value)
            if isinstance(stat_value, str) and '-' in stat_value:
                try: w, l = map(int, stat_value.split('-')); return w / (w + l) if (w + l) > 0 else 0.0
                except ValueError: return 0.0
            try: return float(stat_value)
            except (ValueError, TypeError): print(f"WARN: Unexpected stat format: {stat_value}"); return 0.0

        norm_overall_diff_h = normalize_point_diff(home_stats.get('DiffPointsPG'))
        norm_overall_diff_v = normalize_point_diff(visitor_stats.get('DiffPointsPG'))
        norm_loc_diff_h = normalize_point_diff(home_stats.get('HomePointDiff', home_stats.get('DiffPointsPG')))
        norm_loc_diff_v = normalize_point_diff(visitor_stats.get('RoadPointDiff', visitor_stats.get('DiffPointsPG')))
        norm_l10_diff_h = normalize_point_diff(home_stats.get('L10PointDiff', home_stats.get('DiffPointsPG')))
        norm_l10_diff_v = normalize_point_diff(visitor_stats.get('L10PointDiff', visitor_stats.get('DiffPointsPG')))

        rating_home = ( (get_win_pct(home_stats.get('WinPct', 0.0)) * WEIGHTS['overall_wpct']) + (get_win_pct(home_stats.get('HomeRecord', 0.0)) * WEIGHTS['location_wpct']) + (get_win_pct(home_stats.get('L10Record', 0.0)) * WEIGHTS['last10_wpct']) + (norm_overall_diff_h * WEIGHTS['overall_diff']) + (norm_loc_diff_h * WEIGHTS['location_diff']) + (norm_l10_diff_h * WEIGHTS['last10_diff']) )
        rating_visitor = ( (get_win_pct(visitor_stats.get('WinPct', 0.0)) * WEIGHTS['overall_wpct']) + (get_win_pct(visitor_stats.get('RoadRecord', 0.0)) * WEIGHTS['location_wpct']) + (get_win_pct(visitor_stats.get('L10Record', 0.0)) * WEIGHTS['last10_wpct']) + (norm_overall_diff_v * WEIGHTS['overall_diff']) + (norm_loc_diff_v * WEIGHTS['location_diff']) + (norm_l10_diff_v * WEIGHTS['last10_diff']) )
        print(f"[Calculator] Rating H: {rating_home:.4f}, Rating V: {rating_visitor:.4f}")
    except Exception as e: print(f"!!! Error calculating rating: {e}"); print(f"Home: {home_stats}"); print(f"Visitor: {visitor_stats}"); return None
    total_rating = rating_home + rating_visitor
    if total_rating <= 0: return {"home_win_probability": 0.5, "visitor_win_probability": 0.5}
    prob_home = rating_home / total_rating
    return {"home_win_probability": round(prob_home, 4), "visitor_win_probability": round(1.0 - prob_home, 4)}


# --- Endpoint (sin cambios funcionales) ---
@router.get("/win_probability")
async def get_win_probability_endpoint( home_team_id: int = Query(...), visitor_team_id: int = Query(...) ):
    print(f"[API /predictions/win] Request for H:{home_team_id} vs V:{visitor_team_id}")
    try:
        standings_result = await get_standings_data()
        if not standings_result: raise HTTPException(status_code=503, detail="Could not retrieve standings data.")
        headers = standings_result["headers"]; rows = standings_result["rows"]
        team_stats_map = {}
        try:
            idx_team_id = headers.index('teamid')
            header_map_keys = { 'WinPct': 'winpct', 'HomeRecord': 'home', 'RoadRecord': 'road', 'L10Record': 'l10', 'DiffPointsPG': 'diffpointspg' }
            header_indices = {}
            missing_keys = []
            for key_out, key_in in header_map_keys.items():
                 try: header_indices[key_out] = headers.index(key_in)
                 except ValueError: missing_keys.append(key_in)
            if missing_keys: raise ValueError(f"Missing keys: {missing_keys}")
        except ValueError as e: print(f"!!! Standings Header Error: {e}. Headers: {headers}"); raise HTTPException(status_code=500, detail=f"Standings structure mismatch: {e}")
        for row in rows: t_id = row[idx_team_id]; stats = {key_out: row[idx] for key_out, idx in header_indices.items()}; team_stats_map[t_id] = stats
        home_stats = team_stats_map.get(home_team_id); visitor_stats = team_stats_map.get(visitor_team_id)
        if not home_stats or not visitor_stats: missing = [f"Team ID {tid}" for tid in [home_team_id, visitor_team_id] if tid not in team_stats_map]; raise HTTPException(status_code=404, detail=f"Standings data not found for: {', '.join(missing)}.")
        probabilities = calculate_win_probability(home_stats, visitor_stats)
        if probabilities is None: raise HTTPException(status_code=500, detail="Calculation error.")
        print(f"[API /predictions/win] Calculated Probs: H={probabilities['home_win_probability']:.2%} V={probabilities['visitor_win_probability']:.2%}")
        return probabilities
    except HTTPException as http_exc: raise http_exc
    except Exception as e: print(f"[API /predictions/win] UNEXPECTED Error: {e}"); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"Failed: {str(e)}")
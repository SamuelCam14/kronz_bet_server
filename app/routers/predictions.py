# RUTA: app/routers/predictions.py
from fastapi import APIRouter, HTTPException, Query
from nba_api.stats.endpoints import leaguestandingsv3, leaguedashteamstats
import traceback
import time
import math
import joblib
import os
import numpy as np
import pandas as pd
from datetime import datetime

router = APIRouter()

# --- Configuración ---
SCRIPT_DIR_PRED = os.path.dirname(os.path.abspath(__file__))
APP_ROOT_PRED = os.path.dirname(SCRIPT_DIR_PRED)
PROJECT_ROOT_PRED = os.path.dirname(APP_ROOT_PRED)
MODELS_DIR_PRED = os.path.join(PROJECT_ROOT_PRED, 'models', 'win_probability')
MODEL_FILE_PRED = os.path.join(MODELS_DIR_PRED, "logistic_regression_model.joblib")
SCALER_FILE_PRED = os.path.join(MODELS_DIR_PRED, "scaler.joblib")

FEATURE_COLUMNS = [
    'H_WPCT', 'V_WPCT', 'DIFF_WPCT', 'H_LOC_WPCT', 'V_LOC_WPCT', 'DIFF_LOC_WPCT',
    'H_L10_WPCT', 'V_L10_WPCT', 'DIFF_L10_WPCT', 'H_OFF_RTG', 'V_OFF_RTG', 'DIFF_OFF_RTG',
    'H_DEF_RTG', 'V_DEF_RTG', 'DIFF_DEF_RTG_INV', 'H_NET_RTG', 'V_NET_RTG', 'DIFF_NET_RTG',
    'H_PACE', 'V_PACE', 'DIFF_PACE'
]

API_SLEEP_TIME = 0.7

# --- Carga Modelo y Scaler ---
model = None
scaler = None
try:
    print("[Pred Router] Loading model and scaler...")
    if not os.path.exists(MODEL_FILE_PRED):
        raise FileNotFoundError(f"Model file not found: {MODEL_FILE_PRED}")
    if not os.path.exists(SCALER_FILE_PRED):
        raise FileNotFoundError(f"Scaler file not found: {SCALER_FILE_PRED}")
    model = joblib.load(MODEL_FILE_PRED)
    scaler = joblib.load(SCALER_FILE_PRED)
    print("[Pred Router] Model and scaler loaded successfully.")
except Exception as e:
    print(f"!!! CRITICAL ERROR: Failed to load model or scaler: {e}")
    print("!!! Prediction endpoint WILL FAIL.")
    traceback.print_exc()

# --- Cache y Funciones de Obtención de Datos ---
team_stats_cache = {"data": None, "timestamp": 0, "ttl_seconds": 60 * 15}

# --- fetch_season_standings (CON SINTAXIS CORREGIDA) ---
async def fetch_season_standings(season, season_type="Regular Season"):
    print(f"Fetching Standings for {season} {season_type}...")
    for attempt in range(3):
        try:
            standings = leaguestandingsv3.LeagueStandingsV3(league_id='00', season=season, season_type=season_type)
            data = standings.get_data_frames()
            if data and len(data) > 0:
                print(f"OK Standings {season} {season_type} (Attempt {attempt+1})")
                time.sleep(API_SLEEP_TIME)
                return data[0]
            else:
                print(f"WARN: No standings data {season} {season_type} (Attempt {attempt+1})")
                time.sleep(API_SLEEP_TIME)
                # No retornar aquí, continuar al siguiente intento si es posible
        except Exception as e:
            print(f"!!! API Error (Standings Att {attempt+1}): {e}")
            time.sleep(API_SLEEP_TIME * (attempt + 2))
            # Continuar al siguiente intento
            continue
    # Si todos los intentos fallan
    print(f"!!! FAILED standings {season} {season_type}");
    return None

# --- fetch_season_advanced_stats (CON SINTAXIS CORREGIDA) ---
async def fetch_season_advanced_stats(season, season_type="Regular Season"):
    print(f"Fetching Advanced Stats for {season} {season_type}...")
    for attempt in range(3):
        try:
            stats = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense='Advanced', season=season, season_type_all_star=season_type)
            data = stats.get_data_frames()
        except Exception as e:
            print(f"!!! API Error (Advanced Att {attempt+1}): {e}")
            time.sleep(API_SLEEP_TIME * (attempt + 2))
            continue # Continuar al siguiente intento
        # Separar la comprobación y el retorno
        if data and len(data) > 0:
            print(f"OK Advanced Stats {season} {season_type} (Attempt {attempt+1})")
            time.sleep(API_SLEEP_TIME)
            return data[0]
        else:
            print(f"WARN: No advanced stats {season} {season_type} (Attempt {attempt+1})")
            time.sleep(API_SLEEP_TIME)
            # No retornar aquí, continuar al siguiente intento si es posible
    # Si todos los intentos fallan
    print(f"!!! FAILED advanced {season} {season_type}");
    return None

# --- get_current_season_team_stats (CON SINTAXIS CORREGIDA) ---
async def get_current_season_team_stats():
    now = time.time()
    if team_stats_cache["data"] and (now - team_stats_cache["timestamp"] < team_stats_cache["ttl_seconds"]):
        print("[Team Stats Cache] Using cached combined data.")
        return team_stats_cache["data"]

    print("[Team Stats Cache] Fetching new combined data...")
    combined_team_stats_map = None
    try:
        current_year = datetime.now().year
        current_month = datetime.now().month
        season = f"{current_year-1}-{str(current_year)[-2:]}" if current_month < 9 else f"{current_year}-{str(current_year+1)[-2:]}"
        print(f"[Team Stats Cache] Using season: {season}")

        standings_df = await fetch_season_standings(season, "Regular Season")
        advanced_df = await fetch_season_advanced_stats(season, "Regular Season")

        if standings_df is None or advanced_df is None:
            print("!!! Failed to fetch either standings or advanced stats. Cannot combine.")
            return None

        print("[Team Stats Cache] Combining standings and advanced stats...")
        def find_id_column(df_columns):
            possible_id_names = ['TEAM_ID','TeamID','teamid','team_id']
            for name in possible_id_names:
                 original_name = next((col for col in df_columns if col.lower() == name.lower()), None)
                 if original_name: return original_name
            return None

        standings_id_col = find_id_column(standings_df.columns)
        advanced_id_col = find_id_column(advanced_df.columns)
        if standings_id_col is None or advanced_id_col is None:
             raise ValueError("Team ID column not found for merging.")

        s_df = standings_df.copy(); a_df = advanced_df.copy()
        s_df[standings_id_col] = pd.to_numeric(s_df[standings_id_col], errors='coerce')
        a_df[advanced_id_col] = pd.to_numeric(a_df[advanced_id_col], errors='coerce')
        s_df.dropna(subset=[standings_id_col], inplace=True)
        a_df.dropna(subset=[advanced_id_col], inplace=True)
        s_df[standings_id_col] = s_df[standings_id_col].astype(int)
        a_df[advanced_id_col] = a_df[advanced_id_col].astype(int)
        s_df.columns = s_df.columns.str.lower()
        a_df.columns = a_df.columns.str.lower()
        s_df.rename(columns={standings_id_col.lower(): 'team_id'}, inplace=True)
        a_df.rename(columns={advanced_id_col.lower(): 'team_id'}, inplace=True)
        adv_cols_to_keep = ['team_id', 'off_rating', 'def_rating', 'pace', 'e_off_rating', 'e_def_rating', 'e_pace', 'net_rating', 'e_net_rating']
        adv_cols_existing = [col for col in adv_cols_to_keep if col in a_df.columns]
        advanced_df_subset = a_df[adv_cols_existing]
        combined_df = pd.merge(s_df, advanced_df_subset, on='team_id', how='left')
        combined_df.set_index('team_id', inplace=True)
        combined_team_stats_map = combined_df.to_dict('index')
        team_stats_cache["data"] = combined_team_stats_map
        team_stats_cache["timestamp"] = now
        print(f"[Team Stats Cache] Combined data cached for {len(combined_team_stats_map)} teams.")

    except Exception as e:
        print(f"!!! Exception combining/caching stats: {e}")
        traceback.print_exc()
        combined_team_stats_map = None

    return combined_team_stats_map

# --- Función de Normalización (CON SINTAXIS CORREGIDA) ---
def normalize_point_diff(diff, min_diff=-15.0, max_diff=15.0):
    if diff is None:
        return 0.5
    try:
        diff_float = float(diff)
        clamped_diff = max(min_diff, min(max_diff, diff_float))
        normalized = (clamped_diff - min_diff) / (max_diff - min_diff)
        return normalized
    except (ValueError, TypeError):
        return 0.5

# --- Función Calcular Features (CON SINTAXIS CORREGIDA) ---
def calculate_prediction_features(home_combined_stats, visitor_combined_stats):
    features = {}; missing_keys_log = []
    try:
        def safe_get(stats_dict, key, default=0.0, type_func=float):
            if stats_dict is None: return default
            val = stats_dict.get(key)
            if pd.isna(val) or val is None:
                 if key not in missing_keys_log: missing_keys_log.append(f"{key}(None)")
                 return default
            try:
                 return type_func(val)
            except (ValueError, TypeError):
                 if key not in missing_keys_log: missing_keys_log.append(f"{key}(ConvErr:{type(val)})")
                 return default

        def get_pct_from_record(record_str, default=0.0):
            if isinstance(record_str, str) and '-' in record_str:
                try:
                     w,l=map(int,record_str.split('-'))
                     if (w+l) > 0:
                          return w/(w+l)
                     else:
                          return default
                except ValueError:
                     if f"{record_str}(W-L Err)" not in missing_keys_log: missing_keys_log.append(f"{record_str}(W-L Err)")
                     return default
            try:
                 return float(record_str)
            except (ValueError, TypeError):
                if record_str and f"{record_str}(FloatErr)" not in missing_keys_log: missing_keys_log.append(f"{record_str}(FloatErr)")
                return default

        h_wpct=safe_get(home_combined_stats,'w_pct'); v_wpct=safe_get(visitor_combined_stats,'w_pct')
        h_loc=get_pct_from_record(home_combined_stats.get('home')); v_loc=get_pct_from_record(visitor_combined_stats.get('road'))
        h_l10=get_pct_from_record(home_combined_stats.get('l10')); v_l10=get_pct_from_record(visitor_combined_stats.get('l10'))
        h_off=safe_get(home_combined_stats,'off_rating'); v_off=safe_get(visitor_combined_stats,'off_rating')
        h_def=safe_get(home_combined_stats,'def_rating'); v_def=safe_get(visitor_combined_stats,'def_rating')
        h_pace=safe_get(home_combined_stats,'pace'); v_pace=safe_get(visitor_combined_stats,'pace')
        h_diff=safe_get(home_combined_stats,'plus_minus', default=None); v_diff=safe_get(visitor_combined_stats,'plus_minus', default=None)

        features['H_WPCT']=h_wpct; features['V_WPCT']=v_wpct; features['DIFF_WPCT']=h_wpct-v_wpct
        features['H_LOC_WPCT']=h_loc; features['V_LOC_WPCT']=v_loc; features['DIFF_LOC_WPCT']=h_loc-v_loc
        features['H_L10_WPCT']=h_l10; features['V_L10_WPCT']=v_l10; features['DIFF_L10_WPCT']=h_l10-v_l10
        features['H_OFF_RTG']=h_off; features['V_OFF_RTG']=v_off; features['DIFF_OFF_RTG']=h_off-v_off
        features['H_DEF_RTG']=h_def; features['V_DEF_RTG']=v_def; features['DIFF_DEF_RTG_INV']=v_def-h_def
        features['H_NET_RTG']=h_off-h_def; features['V_NET_RTG']=v_off-v_def; features['DIFF_NET_RTG']=(h_off-h_def)-(v_off-v_def)
        features['H_PACE']=h_pace; features['V_PACE']=v_pace; features['DIFF_PACE']=h_pace-v_pace

        if missing_keys_log: print(f"[Feature Calc] WARN: Missing/ConvErr: {missing_keys_log}")
        ordered_features = [features.get(col_name, 0.0) for col_name in FEATURE_COLUMNS]
        return ordered_features
    except Exception as e: print(f"!!! Error calculating features: {e}"); print(f"H_Stats:{home_combined_stats}"); print(f"V_Stats:{visitor_combined_stats}"); traceback.print_exc(); return None

# --- Endpoint de Predicción (CON SINTAXIS CORREGIDA) ---
@router.get("/win_probability")
async def predict_win_probability( home_team_id: int = Query(...), visitor_team_id: int = Query(...) ):
    print(f"[API Predict] Request for H:{home_team_id} vs V:{visitor_team_id}")
    if model is None or scaler is None:
        raise HTTPException(status_code=503, detail="Prediction model not ready.")
    try:
        combined_stats_map = await get_current_season_team_stats()
        if not combined_stats_map:
            raise HTTPException(status_code=503, detail="Could not retrieve current team stats.")
        home_stats = combined_stats_map.get(home_team_id)
        visitor_stats = combined_stats_map.get(visitor_team_id)
        if not home_stats or not visitor_stats:
            raise HTTPException(status_code=404, detail="Current stats not found for one or both teams.")

        features = calculate_prediction_features(home_stats, visitor_stats)
        if features is None:
            raise HTTPException(status_code=500, detail="Feature calculation failed.")

        features_array = np.array(features).reshape(1, -1)
        features_scaled = scaler.transform(features_array)
        print(f"[API Predict] Features calculated & scaled: {np.round(features_scaled, 3)}")

        probabilities = model.predict_proba(features_scaled)[0]
        prob_home_win = probabilities[1]
        prob_visitor_win = probabilities[0]

        print(f"[API Predict] Predicted Probs: H={prob_home_win:.4f} V={prob_visitor_win:.4f}")
        return {"home_win_probability": round(prob_home_win, 4), "visitor_win_probability": round(prob_visitor_win, 4)}
    except HTTPException as http_exc:
        # Re-lanzar excepciones HTTP que ya generamos
        raise http_exc
    except Exception as e:
        print(f"[API Predict] UNEXPECTED Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")
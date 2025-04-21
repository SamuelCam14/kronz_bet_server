# RUTA: server_py/scripts/build_features.py
import sqlite3
import pandas as pd
from nba_api.stats.endpoints import leaguedashteamstats, leaguestandingsv3
import time
import traceback
from datetime import datetime
import os

# --- Configuración ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
DATABASE_NAME = os.path.join(DATA_DIR, "nba_data.db")
FEATURES_OUTPUT_FILE = os.path.join(DATA_DIR, "nba_game_features.csv")
SEASONS_TO_PROCESS = ["2023-24", "2022-23"]
SEASON_TYPES = ["Regular Season", "Playoffs"]
API_SLEEP_TIME = 0.7

# --- Funciones Auxiliares ---

def create_connection(db_file_path):
    """ Crea una conexión a la base de datos SQLite usando ruta absoluta """
    conn = None
    try:
        conn = sqlite3.connect(db_file_path)
        print(f"SQLite DB connection successful to {db_file_path}")
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
    # Return va fuera del try/except
    return conn

def fetch_season_advanced_stats(season, season_type="Regular Season"):
    """ Obtiene stats avanzadas (Pace, Ratings) para todos los equipos en una temporada/tipo """
    print(f"Fetching Advanced Stats for {season} {season_type}...")
    for attempt in range(3):
        try:
            stats = leaguedashteamstats.LeagueDashTeamStats(
                measure_type_detailed_defense='Advanced',
                season=season,
                season_type_all_star=season_type
            )
            data = stats.get_data_frames()
            if data and len(data) > 0:
                print(f"OK Advanced Stats for {season} {season_type} (Attempt {attempt+1})")
                time.sleep(API_SLEEP_TIME)
                return data[0]
            else:
                print(f"WARN: No advanced stats data returned (Attempt {attempt+1}) for {season} {season_type}")
                time.sleep(API_SLEEP_TIME) # Pausar incluso si no hay datos
                # No retornar None aquí, permitir reintento
        except Exception as e:
            print(f"!!! API Request Error (Advanced Stats Attempt {attempt+1}, {season} {season_type}): {e}")
            time.sleep(API_SLEEP_TIME * (attempt + 2)) # Pausa más larga en error
            # Continuar al siguiente intento
    # Si todos los intentos fallan
    print(f"!!! FAILED to fetch advanced stats for {season} {season_type} after 3 attempts.")
    return None

def fetch_season_standings(season, season_type="Regular Season"):
    """ Obtiene standings (Wpct, L10, Home/Road) para todos los equipos """
    print(f"Fetching Standings for {season} {season_type}...")
    for attempt in range(3):
        try:
            standings = leaguestandingsv3.LeagueStandingsV3(
                league_id='00',
                season=season,
                season_type=season_type
            )
            data = standings.get_data_frames()
            if data and len(data) > 0:
                print(f"OK Standings for {season} {season_type} (Attempt {attempt+1})")
                time.sleep(API_SLEEP_TIME)
                return data[0]
            else:
                print(f"WARN: No standings data returned (Attempt {attempt+1}) for {season} {season_type}")
                time.sleep(API_SLEEP_TIME)
        except Exception as e:
            print(f"!!! API Request Error (Standings Attempt {attempt+1}, {season} {season_type}): {e}")
            time.sleep(API_SLEEP_TIME * (attempt + 2))
    print(f"!!! FAILED to fetch standings for {season} {season_type} after 3 attempts.")
    return None

def normalize_point_diff(diff, min_diff=-15.0, max_diff=15.0):
    """ Normaliza el diferencial de puntos a una escala 0-1. """
    if diff is None:
        return 0.5
    try:
        diff_float = float(diff)
        clamped_diff = max(min_diff, min(max_diff, diff_float))
        normalized = (clamped_diff - min_diff) / (max_diff - min_diff)
        return normalized
    except (ValueError, TypeError):
        return 0.5

# --- Función Principal ---
def build_features():
    print("Starting feature building process...")
    conn = create_connection(DATABASE_NAME)
    if conn is None:
        print("Cannot proceed: No database connection.")
        return

    try:
        # 1. Cargar juegos históricos
        print("Loading historical games from database...")
        query = "SELECT * FROM games WHERE HOME_TEAM_ID IS NOT NULL AND VISITOR_TEAM_ID IS NOT NULL ORDER BY GAME_DATE ASC"
        try:
            all_games_df = pd.read_sql_query(query, conn)
            print(f"Loaded {len(all_games_df)} valid games from DB.")
            # Limpieza y conversión de tipos
            all_games_df['GAME_DATE'] = pd.to_datetime(all_games_df['GAME_DATE'])
            for col in ['HOME_PTS', 'VISITOR_PTS', 'HOME_TEAM_ID', 'VISITOR_TEAM_ID']:
                all_games_df[col] = pd.to_numeric(all_games_df[col], errors='coerce')
            all_games_df.dropna(subset=['HOME_TEAM_ID', 'VISITOR_TEAM_ID'], inplace=True)
            all_games_df[['HOME_TEAM_ID', 'VISITOR_TEAM_ID']] = all_games_df[['HOME_TEAM_ID', 'VISITOR_TEAM_ID']].astype(int)
        except Exception as e:
            print(f"Error reading or processing games from DB: {e}")
            traceback.print_exc()
            # Salir si no podemos cargar los juegos base
            return

        # 2. Obtener y cachear stats de temporada
        season_stats_cache = {}
        print("\n--- Fetching and Caching Seasonal Stats ---")
        for season in SEASONS_TO_PROCESS:
            for season_type in SEASON_TYPES:
                cache_key = f"{season}_{season_type.replace(' ', '')}"
                print(f"--- Preparing stats for {cache_key} ---")
                standings_df = fetch_season_standings(season, season_type)
                advanced_df = fetch_season_advanced_stats(season, season_type)

                if standings_df is not None and advanced_df is not None:
                     try:
                         # Función interna clara para encontrar columna ID
                         def find_id_column(df_columns):
                             possible_id_names = ['TEAM_ID','TeamID','teamid','team_id']
                             for name in possible_id_names:
                                 # Comprobar existencia insensible a mayúsculas/minúsculas pero devolver original
                                 original_name = next((col for col in df_columns if col.lower() == name), None)
                                 if original_name:
                                     return original_name
                             return None

                         standings_id_col = find_id_column(standings_df.columns)
                         advanced_id_col = find_id_column(advanced_df.columns)

                         if standings_id_col is None:
                              raise KeyError(f"Standings DataFrame missing common ID column. Found: {standings_df.columns.tolist()}")
                         if advanced_id_col is None:
                              raise KeyError(f"Advanced Stats DataFrame missing common ID column. Found: {advanced_df.columns.tolist()}")

                         print(f"Found Standings ID Col: '{standings_id_col}', Advanced Stats ID Col: '{advanced_id_col}'")

                         # Trabajar con copias para evitar warnings
                         s_df = standings_df.copy()
                         a_df = advanced_df.copy()

                         # Establecer índice y convertir columnas a minúsculas
                         s_df.set_index(standings_id_col, inplace=True)
                         a_df.set_index(advanced_id_col, inplace=True)
                         s_df.columns = s_df.columns.str.lower()
                         a_df.columns = a_df.columns.str.lower()

                         season_stats_cache[cache_key] = {"standings": s_df, "advanced": a_df}
                     except KeyError as ke:
                         print(f"WARN: Could not set index for {cache_key}. Stats might be incomplete. Error: {ke}")
                         season_stats_cache[cache_key] = {"standings": None, "advanced": None} # Marcar como inválido
                else:
                    print(f"WARN: Could not fetch complete stats for {cache_key}.")
        print("--- Finished Fetching Seasonal Stats ---")

        # 3. Calcular features por juego
        print("\n--- Calculating features for each game ---")
        game_features_list = []
        processed_count = 0
        skipped_count = 0

        for index, game in all_games_df.iterrows():
            cache_key = f"{game['SEASON_YEAR']}_{game['SEASON_TYPE'].replace(' ', '')}"

            # Saltar si no hay datos de temporada para este juego
            if cache_key not in season_stats_cache or \
               season_stats_cache[cache_key]["standings"] is None or \
               season_stats_cache[cache_key]["advanced"] is None:
                skipped_count += 1
                continue

            home_id = game['HOME_TEAM_ID']
            visitor_id = game['VISITOR_TEAM_ID']
            standings = season_stats_cache[cache_key]["standings"]
            advanced = season_stats_cache[cache_key]["advanced"]

            # Extraer stats para ambos equipos
            home_s = standings.loc[home_id] if home_id in standings.index else None
            visitor_s = standings.loc[visitor_id] if visitor_id in standings.index else None
            home_a = advanced.loc[home_id] if home_id in advanced.index else None
            visitor_a = advanced.loc[visitor_id] if visitor_id in advanced.index else None

            # Saltar si falta algún dato de equipo
            if home_s is None or visitor_s is None or home_a is None or visitor_a is None:
                skipped_count += 1
                continue

            # --- Helpers para extraer datos de forma segura ---
            def safe_get(series, key, default=0.0, type_func=float):
                """ Extrae un valor de una Serie de Pandas de forma segura. """
                if series is None or key not in series.index:
                    return default
                val = series.get(key)
                if pd.isna(val) or val is None:
                    return default
                try:
                    return type_func(val)
                except (ValueError, TypeError):
                    return default

            def get_pct_from_record(record_str, default=0.0):
                """ Calcula porcentaje de victorias desde un string 'W-L'. """
                if isinstance(record_str, str) and '-' in record_str:
                    try:
                        w, l = map(int, record_str.split('-'))
                        if (w + l) > 0:
                            return w / (w + l)
                        else:
                            return default
                    except ValueError:
                        return default
                return default

            # --- Extracción de Features ---
            # (Verifica estas claves minúsculas con los headers impresos por fetch_ funciones)
            h_wpct=safe_get(home_s,'w_pct')
            v_wpct=safe_get(visitor_s,'w_pct')
            h_loc=get_pct_from_record(home_s.get('home')) # home record 'W-L'
            v_loc=get_pct_from_record(visitor_s.get('road')) # road record 'W-L'
            h_l10=get_pct_from_record(home_s.get('l10')) # l10 record 'W-L'
            v_l10=get_pct_from_record(visitor_s.get('l10'))
            # Asegúrate que los nombres 'off_rating', 'def_rating', 'pace' sean correctos
            h_off=safe_get(home_a,'off_rating')
            v_off=safe_get(visitor_a,'off_rating')
            h_def=safe_get(home_a,'def_rating')
            v_def=safe_get(visitor_a,'def_rating')
            h_pace=safe_get(home_a,'pace')
            v_pace=safe_get(visitor_a,'pace')
            # Usaremos 'plus_minus' de standings como proxy para diffpointspg
            h_diff=safe_get(home_s,'plus_minus', default=None)
            v_diff=safe_get(visitor_s,'plus_minus', default=None)

            # Calcular Diferenciales
            diff_wpct=h_wpct-v_wpct
            diff_loc=h_loc-v_loc
            diff_l10=h_l10-v_l10
            diff_off=h_off-v_off
            diff_def_inv=v_def-h_def # Queremos V-H (mayor es mejor para el local)
            diff_net=(h_off-h_def)-(v_off-v_def)
            diff_pace=h_pace-v_pace

            home_win = 1 if game['WL_HOME'] == 'W' else 0

            # Añadir fila al listado
            game_features_list.append({
                'GAME_ID': game['GAME_ID'], 'GAME_DATE': game['GAME_DATE'].strftime('%Y-%m-%d'),
                'SEASON_YEAR': game['SEASON_YEAR'], 'HOME_TEAM_ID': home_id, 'VISITOR_TEAM_ID': visitor_id,
                'HOME_TEAM_ABBR': game['HOME_TEAM_ABBREVIATION'], 'VISITOR_TEAM_ABBR': game['VISITOR_TEAM_ABBREVIATION'],
                'HOME_WIN': home_win,
                'H_WPCT': h_wpct, 'V_WPCT': v_wpct, 'DIFF_WPCT': diff_wpct,
                'H_LOC_WPCT': h_loc, 'V_LOC_WPCT': v_loc, 'DIFF_LOC_WPCT': diff_loc,
                'H_L10_WPCT': h_l10, 'V_L10_WPCT': v_l10, 'DIFF_L10_WPCT': diff_l10,
                'H_OFF_RTG': h_off, 'V_OFF_RTG': v_off, 'DIFF_OFF_RTG': diff_off,
                'H_DEF_RTG': h_def, 'V_DEF_RTG': v_def, 'DIFF_DEF_RTG_INV': diff_def_inv,
                'H_NET_RTG': h_off-h_def, 'V_NET_RTG': v_off-v_def, 'DIFF_NET_RTG': diff_net,
                'H_PACE': h_pace, 'V_PACE': v_pace, 'DIFF_PACE': diff_pace
            })
            processed_count += 1
            if processed_count % 100 == 0:
                print(f"Processed features for {processed_count} games...")

        # 4. Crear DataFrame final y guardar
        print(f"\nFinished feature calculation. Processed: {processed_count}, Skipped: {skipped_count}")
        if not game_features_list:
            print("No features were generated.")
            return # Salir si no hay nada que guardar

        features_df = pd.DataFrame(game_features_list)
        # Reordenar columnas para legibilidad
        column_order = [
            'GAME_ID','GAME_DATE','SEASON_YEAR','HOME_TEAM_ID','VISITOR_TEAM_ID',
            'HOME_TEAM_ABBR','VISITOR_TEAM_ABBR','HOME_WIN', # Target
            'H_WPCT','V_WPCT','DIFF_WPCT',
            'H_LOC_WPCT','V_LOC_WPCT','DIFF_LOC_WPCT',
            'H_L10_WPCT','V_L10_WPCT','DIFF_L10_WPCT',
            'H_OFF_RTG','V_OFF_RTG','DIFF_OFF_RTG',
            'H_DEF_RTG','V_DEF_RTG','DIFF_DEF_RTG_INV',
            'H_NET_RTG','V_NET_RTG','DIFF_NET_RTG',
            'H_PACE','V_PACE','DIFF_PACE'
        ]
        # Filtra por columnas que realmente existen en el DF
        final_columns = [col for col in column_order if col in features_df.columns]
        features_df = features_df[final_columns]

        print(f"Saving features for {len(features_df)} games to '{FEATURES_OUTPUT_FILE}'...")
        # Asegurarse que el directorio exista
        os.makedirs(os.path.dirname(FEATURES_OUTPUT_FILE), exist_ok=True)
        features_df.to_csv(FEATURES_OUTPUT_FILE, index=False)
        print("Features saved successfully.")

    except Exception as e:
        print(f"An error occurred during the build_features process: {e}")
        traceback.print_exc()
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    build_features()
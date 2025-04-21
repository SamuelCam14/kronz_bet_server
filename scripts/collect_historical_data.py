# RUTA: server_py/scripts/collect_historical_data.py
import sqlite3
import time
from datetime import datetime
from nba_api.stats.endpoints import leaguegamelog
import traceback
import os # Asegúrate que os esté importado

# --- Configuración (Definir rutas absolutas) ---
# Obtener la ruta del directorio donde está el script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Subir un nivel para llegar a la raíz del proyecto (server_py)
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
# Definir la ruta a la carpeta de datos
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
# Crear la carpeta de datos si no existe
os.makedirs(DATA_DIR, exist_ok=True)
# *** RUTA ABSOLUTA para la base de datos ***
DATABASE_FILE_PATH = os.path.join(DATA_DIR, "nba_data.db")

SEASONS_TO_FETCH = ["2023-24", "2022-23"]
SEASON_TYPES = ["Regular Season", "Playoffs"]
API_SLEEP_TIME = 0.6

# --- Funciones Auxiliares (create_connection USA LA RUTA ABSOLUTA) ---

def create_connection(db_file_path): # Renombrado parámetro para claridad
    """ Crea una conexión a la base de datos SQLite usando ruta absoluta """
    conn = None
    try:
        # *** USA LA RUTA ABSOLUTA DIRECTAMENTE ***
        conn = sqlite3.connect(db_file_path)
        print(f"SQLite DB connection successful to {db_file_path}")
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
    return conn

def create_table(conn):
    """ Crea la tabla 'games' si no existe """
    # SQL sin cambios
    sql_create_games_table = """ CREATE TABLE IF NOT EXISTS games ( GAME_ID TEXT PRIMARY KEY, SEASON_YEAR TEXT NOT NULL, GAME_DATE TEXT NOT NULL, MATCHUP TEXT, HOME_TEAM_ID INTEGER, HOME_TEAM_ABBREVIATION TEXT, VISITOR_TEAM_ID INTEGER, VISITOR_TEAM_ABBREVIATION TEXT, HOME_PTS INTEGER, VISITOR_PTS INTEGER, WL_HOME TEXT, WL_VISITOR TEXT, PLUS_MINUS_HOME REAL, PLUS_MINUS_VISITOR REAL, SEASON_TYPE TEXT NOT NULL ); """
    try: cursor = conn.cursor(); cursor.execute(sql_create_games_table); print("Table 'games' checked/created.");
    except sqlite3.Error as e: print(f"Error creating table: {e}")

def insert_game_data(conn, game_data):
    """ Inserta o reemplaza una fila de datos de juego """
    sql = ''' INSERT OR REPLACE INTO games( GAME_ID, SEASON_YEAR, GAME_DATE, MATCHUP, HOME_TEAM_ID, HOME_TEAM_ABBREVIATION, VISITOR_TEAM_ID, VISITOR_TEAM_ABBREVIATION, HOME_PTS, VISITOR_PTS, WL_HOME, WL_VISITOR, PLUS_MINUS_HOME, PLUS_MINUS_VISITOR, SEASON_TYPE ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) '''
    try: cursor = conn.cursor(); cursor.execute(sql, game_data); conn.commit(); return cursor.lastrowid
    except sqlite3.Error as e: print(f"Error inserting {game_data[0]}: {e}"); return None

# --- Función fetch_and_store_gamelog (SIN CAMBIOS) ---
def fetch_and_store_gamelog(conn, season, season_type):
    # ... (Código exacto de la función anterior sin cambios)...
    print(f"\n--- Fetching {season_type} data for {season} ---"); processed_games = 0
    try:
        gamelog = leaguegamelog.LeagueGameLog( season=season, season_type_all_star=season_type, league_id='00' ); log_data = gamelog.get_dict()
        if not log_data or 'resultSets' not in log_data or not log_data['resultSets']: print(f"WARN: No data for {season} {season_type}"); return 0
        game_set = log_data['resultSets'][0]
        if 'headers' not in game_set or 'rowSet' not in game_set: print(f"WARN: Missing structure {season} {season_type}"); return 0
        headers = [h.lower() for h in game_set['headers']]; rows = game_set['rowSet']
        print(f"Found {len(rows)} game entries in log."); # print(f"Headers found: {headers}") # Log opcional
        try: idx_season_id=headers.index('season_id'); idx_game_id=headers.index('game_id'); idx_game_date=headers.index('game_date'); idx_matchup=headers.index('matchup'); idx_team_id=headers.index('team_id'); idx_team_abbr=headers.index('team_abbreviation'); idx_wl=headers.index('wl'); idx_pts=headers.index('pts'); idx_plus_minus=headers.index('plus_minus')
        except ValueError as e: print(f"!!! Header Error: Missing '{e}'. Headers: {headers}"); return 0
        games_buffer = {}
        for row in rows:
            if len(row) <= max(idx_season_id, idx_game_id, idx_game_date, idx_matchup, idx_team_id, idx_team_abbr, idx_wl, idx_pts, idx_plus_minus): print(f"WARN: Row length mismatch, skipping. Row: {row}"); continue
            try:
                game_id = row[idx_game_id]; game_date = row[idx_game_date].split('T')[0]; matchup = row[idx_matchup].strip(); team_abbr = row[idx_team_abbr]
                team_data = { "team_id": row[idx_team_id], "abbr": team_abbr, "wl": row[idx_wl], "pts": int(row[idx_pts]) if row[idx_pts] is not None else 0, "plus_minus": float(row[idx_plus_minus]) if row[idx_plus_minus] is not None else 0.0 }
                if game_id not in games_buffer: games_buffer[game_id] = { "game_date": game_date, "matchup": matchup, "season_year": season, "home": None, "visitor": None }
                is_home = f"@{team_abbr}" in matchup or f"{team_abbr} vs." in matchup; is_visitor = f"{team_abbr} @" in matchup or f"vs. {team_abbr}" in matchup
                if is_home:
                    if games_buffer[game_id]["home"] is None: games_buffer[game_id]["home"] = team_data
                    else: print(f"WARN: Assigning home {team_abbr} twice for game {game_id}")
                elif is_visitor:
                     if games_buffer[game_id]["visitor"] is None: games_buffer[game_id]["visitor"] = team_data
                     else: print(f"WARN: Assigning visitor {team_abbr} twice for game {game_id}")
                else: print(f"WARN: Could not determine home/visitor for {team_abbr} in '{matchup}' game {game_id}")
            except Exception as row_err: print(f"Error processing row: {row_err}. Row data: {row}"); continue
        print(f"Processing {len(games_buffer)} unique games...")
        for game_id, data in games_buffer.items():
            home = data.get("home"); visitor = data.get("visitor")
            if home and visitor:
                game_to_insert = ( game_id, data["season_year"], data["game_date"], data["matchup"], home.get("team_id"), home.get("abbr"), visitor.get("team_id"), visitor.get("abbr"), home.get("pts"), visitor.get("pts"), home.get("wl"), visitor.get("wl"), home.get("plus_minus"), visitor.get("plus_minus"), season_type )
                if insert_game_data(conn, game_to_insert): processed_games += 1
            else: print(f"WARN: Missing home or visitor data for game {game_id}. Buffer: {data}. Skipping.")
        print(f"--- Finished processing {processed_games} games for {season} {season_type} ---")
        return processed_games
    except Exception as e: print(f"!!! UNEXPECTED Error fetching/processing {season} {season_type}: {e}"); traceback.print_exc(); return processed_games

# --- Función Principal (Modificada para usar RUTA ABSOLUTA) ---
def main():
    print("Starting historical data collection...")
    # *** USA LA RUTA ABSOLUTA AL CREAR LA CONEXIÓN ***
    conn = create_connection(DATABASE_FILE_PATH) # Pasa la ruta completa

    if conn is not None:
        try:
            create_table(conn)
            total_games_processed = 0; start_time = time.time()
            for season in SEASONS_TO_FETCH:
                for season_type in SEASON_TYPES:
                    games_count = fetch_and_store_gamelog(conn, season, season_type)
                    total_games_processed += games_count
                    print(f"Sleeping for {API_SLEEP_TIME} seconds...")
                    time.sleep(API_SLEEP_TIME)
            end_time = time.time()
            print("\n=============================================="); print(f"Data collection finished."); print(f"Total games processed: {total_games_processed}"); print(f"Total time: {end_time - start_time:.2f} seconds");
            # *** Imprime la ruta donde se guardó ***
            print(f"Data saved to {DATABASE_FILE_PATH}")
            print("==============================================")
        finally:
             conn.close(); print("Database connection closed.")
    else: print("Failed to create database connection. Aborting.")

if __name__ == '__main__':
    main()
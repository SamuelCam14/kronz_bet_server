# RUTA: app/utils/data_transformer.py
from datetime import datetime
import pytz
import traceback # Para imprimir errores

def transform_boxscore_data(raw_player_stats, headers_lower_with_team): # Recibe headers aplanados + teaminfo
    """Transforms raw player stats data (flattened) from BoxScoreTraditionalV3."""
    transformed = []
    if not raw_player_stats or not headers_lower_with_team:
        print("[Transformer V3 Flat] Received empty raw_player_stats or headers.")
        return transformed

    headers_lower = headers_lower_with_team # Usamos el nombre completo para claridad

    # --- Búsqueda de Índices (AHORA EN LA LISTA APLANADA) ---
    # Claves requeridas (minúsculas) - Ahora incluyendo teamid/tricode que añadimos
    required_keys = ['personid', 'firstname', 'familyname', 'teamid', 'teamtricode']
    # Claves opcionales (minúsculas) que esperamos (originalmente dentro de 'statistics')
    optional_keys = [
        'minutes', 'points', 'reboundstotal', 'assists', 'fieldgoalsmade', 'fieldgoalsattempted',
        'fieldgoalspercentage', 'threepointersmade', 'threepointersattempted', 'threepointerspercentage',
        'freethrowsmade', 'freethrowsattempted', 'freethrowspercentage', 'reboundsoffensive',
        'reboundsdefensive', 'steals', 'blocks', 'turnovers', 'foulspersonal', 'plusminuspoints'
    ]
    # Añadir claves principales que no son stats (también opcionales por si acaso)
    optional_keys.extend(['namei', 'playerslug', 'position', 'comment', 'jerseynum'])


    indices = {}
    missing_required = []

    # Busca índices requeridos
    for key in required_keys:
        try:
            indices[key] = headers_lower.index(key)
        except ValueError:
            missing_required.append(key)

    if missing_required:
        print(f"!!! Box Score Transformer V3 Flat Error: Missing REQUIRED keys: {missing_required}. Headers found: {headers_lower}")
        if raw_player_stats: print("First row example:", raw_player_stats[0])
        return []

    # Busca índices opcionales
    for key in optional_keys:
        try:
            indices[key] = headers_lower.index(key)
        except ValueError:
            indices[key] = -1
            # print(f"[Transformer V3 Flat] Optional key '{key}' not found.")

    print(f"[Transformer V3 Flat] Found indices: {indices}")

    # --- Itera y transforma cada fila (jugador) ---
    for i, row in enumerate(raw_player_stats):
        try:
            # Función helper para obtener valor de forma segura usando el índice encontrado
            def get_value(key, default=None):
                idx = indices.get(key, -1)
                # Verifica que el índice no esté fuera de los límites de la fila
                if idx != -1 and idx < len(row):
                    return row[idx]
                return default

            # Función helper para obtener stat numérico
            def get_stat(key, type_func=int, default=None):
                value = get_value(key)
                if value is None or value == '': return default
                try: return type_func(value)
                except (ValueError, TypeError): return default

            # --- Extrae datos usando los índices encontrados ---
            player_id = get_value('personid')
            first_name = get_value('firstname')
            last_name = get_value('familyname')
            team_id = str(get_value('teamid', '')) # Obtiene de la columna añadida
            team_abbr = get_value('teamtricode') # Obtiene de la columna añadida

            transformed_player = {
                "player": {"id": player_id, "first_name": first_name, "last_name": last_name},
                "team": {"abbreviation": team_abbr, "nba_team_id": team_id},
                # Mapea las stats usando los nombres V3 como clave para get_stat
                "min": get_value('minutes', '-'),
                "pts": get_stat('points', default=0),
                "reb": get_stat('reboundstotal', default=0),
                "ast": get_stat('assists', default=0),
                "fgm": get_stat('fieldgoalsmade'),
                "fga": get_stat('fieldgoalsattempted'),
                "fg_pct": get_stat('fieldgoalspercentage', float),
                "fg3m": get_stat('threepointersmade'),
                "fg3a": get_stat('threepointersattempted'),
                "fg3_pct": get_stat('threepointerspercentage', float),
                "ftm": get_stat('freethrowsmade'),
                "fta": get_stat('freethrowsattempted'),
                "ft_pct": get_stat('freethrowspercentage', float),
                "oreb": get_stat('reboundsoffensive'),
                "dreb": get_stat('reboundsdefensive'),
                "stl": get_stat('steals'),
                "blk": get_stat('blocks'),
                "tov": get_stat('turnovers'),
                "pf": get_stat('foulspersonal'),
                "plus_minus": get_stat('plusminuspoints', default=0), # +/-
            }
            transformed.append(transformed_player)

        except IndexError:
            print(f"!!! Transformer V3 Flat IndexError on row {i}. Row length: {len(row)}. Indices: {indices}")
            continue
        except Exception as e:
             print(f"!!! Transformer V3 Flat general error on row {i}: {e}. Row data: {row}")
             traceback.print_exc()
             continue

    print(f"[Transformer V3 Flat] Finished transforming {len(transformed)} player stats.")
    return transformed
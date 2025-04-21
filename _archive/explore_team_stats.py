# explore_team_stats.py
from nba_api.stats.endpoints import leaguedashteamstats
import json
import traceback

try:
    # *** CAMBIO: Usar measure_type 'Advanced' ***
    print("\n=== Fetching ADVANCED Stats ===")
    team_stats_advanced = leaguedashteamstats.LeagueDashTeamStats(
        measure_type_detailed_defense='Advanced', # CAMBIADO A ADVANCED
        season='2023-24',
        season_type_all_star='Regular Season'
        # per_mode_detailed='PerGame' # O Per100Possessions
    )
    stats_dict_advanced = team_stats_advanced.get_dict()

    if stats_dict_advanced and 'resultSets' in stats_dict_advanced and stats_dict_advanced['resultSets']:
        main_set_advanced = stats_dict_advanced['resultSets'][0]
        headers_advanced = main_set_advanced.get('headers')
        rows_advanced = main_set_advanced.get('rowSet')

        if not headers_advanced or not rows_advanced:
             print("WARN: Advanced Stats - Headers or RowSet is empty.")
        else:
            print("--- LeagueDashTeamStats Headers (Advanced) ---")
            print(headers_advanced)
            print("\n--- Example Row (Advanced - First Team) ---")
            first_team_stats_advanced = dict(zip(headers_advanced, rows_advanced[0]))
            print(json.dumps(first_team_stats_advanced, indent=2))

            # Buscar métricas clave avanzadas
            print("\n--- Checking for Key Advanced Metrics ---")
            headers_set_lower_adv = set(h.lower() for h in headers_advanced)
            # Nombres comunes para ratings/pace (¡verifica la salida!)
            print(f"PACE available? {'pace' in headers_set_lower_adv}")
            print(f"OFF_RATING available? {'off_rating' in headers_set_lower_adv}")
            print(f"DEF_RATING available? {'def_rating' in headers_set_lower_adv}")
            print(f"NET_RATING available? {'net_rating' in headers_set_lower_adv}")
            # A veces usan prefijo E_
            print(f"E_PACE available? {'e_pace' in headers_set_lower_adv}")
            print(f"E_OFF_RATING available? {'e_off_rating' in headers_set_lower_adv}")
            print(f"E_DEF_RATING available? {'e_def_rating' in headers_set_lower_adv}")
            print(f"E_NET_RATING available? {'e_net_rating' in headers_set_lower_adv}")

    else:
        print("Could not retrieve advanced data or structure is unexpected.")

except Exception as e:
    print(f"An error occurred fetching advanced stats: {e}")
    traceback.print_exc()
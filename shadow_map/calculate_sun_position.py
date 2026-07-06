from suncalc import get_position
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import math
import pickle

LAT  = 52.13896498167249
LON  = 11.645601397328756
YEAR = 2026

def deg(radians: float) -> float:
    return math.degrees(radians)

def calculate_min_max_range(sun_position_table):
    all_az  = [v[0] for v in sun_position_table.values()]
    all_alt = [v[1] for v in sun_position_table.values()]

    az_min,  az_max  = min(all_az),  max(all_az)
    alt_min, alt_max = min(all_alt), max(all_alt)

    print("\nRanges (above-horizon only)")
    print(f"\tAzimuth: {az_min:.4f}°  →  {az_max:.4f}°  (span {az_max - az_min:.2f}°)")
    print(f"\tAltitude: {alt_min:.4f}°  →  {alt_max:.4f}°  (span {alt_max - alt_min:.2f}°)")   

def calculate_sun_positions_min(lat=LAT, lon=LON, year=YEAR):
    start = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(year+1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    step = timedelta(minutes=1)

    # Table: datetime string: az, alt
    sun_position_table: dict[str, tuple[float, float]] = {}

    current = start
    while current < end:
        sun_pos = get_position(current, lon, lat)
        alt = deg(float(sun_pos["altitude"]))
        az = (deg(float(sun_pos["azimuth"])) + 180) % 360

        # Only saving for sun above horizon
        if alt >= 2:
            sun_position_table[current.strftime(("%Y-%m-%d %H:%M"))] = (round(az, 4), round(alt, 4))
        
        current += step

    total_minutes = 365*24*60
    above_horizon_minutes = len(sun_position_table)

    print(f"\nTotal minutes in 2026: {total_minutes:,}")
    print(f"Above-horizon minutes: {above_horizon_minutes:,}  ({above_horizon_minutes/total_minutes*100:.1f}%)")

    calculate_min_max_range(sun_position_table)
    return sun_position_table


def create_1_degree_grid_table(sun_position_table):
    # Create a dict to store 1°/1° grid sun position table
    # Key: azimuth and altitude rounded to nearest 1°
    # Value: list of all pairs (az, alt) that fall in this range
    grid_sun_position_table: dict[tuple[int, int], list[tuple[float, float, str]]] = defaultdict(list)

    for datetime_str, (az, alt) in sun_position_table.items():
        grid_key = (round(az), round(alt))
        grid_sun_position_table[grid_key].append((az, alt, datetime_str))

    n_cells = len(grid_sun_position_table)
    print(f"\nNumber of cells: {n_cells}")

    list_grid_pos = list(grid_sun_position_table.keys())

    with open("grid_sun_pos.pkl", "wb") as f:
        pickle.dump(list_grid_pos, f)


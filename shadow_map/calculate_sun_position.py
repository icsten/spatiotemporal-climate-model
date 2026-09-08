from suncalc import get_position
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import math
import pickle
 
from config import LAT, LON, YEAR, ALT_MIN, SUN_POSITION_GRID_PATH

def get_sun_position(dt: datetime, lon: float, lat: float) -> tuple[float, float]:
    """Return (altitude_deg, azimuth_deg) for a given time and location."""
    sun_pos = get_position(dt, lon, lat)
    alt = math.degrees(float(sun_pos["altitude"]))
    az = (math.degrees(float(sun_pos["azimuth"])) + 180) % 360
    return alt, az

def round_sun_position(alt: float, az: float) -> tuple[int, int]:
    """Snap a raw sun position to the 1-degree grid used for precomputed shadows."""
    return round(alt), round(az) % 360

def calculate_min_max_range(sun_position_table):
    all_az  = [v[0] for v in sun_position_table.values()]
    all_alt = [v[1] for v in sun_position_table.values()]

    az_min,  az_max  = min(all_az),  max(all_az)
    alt_min, alt_max = min(all_alt), max(all_alt)

    print("\nRanges (above-horizon only)")
    print(f"\tAzimuth: {az_min:.4f}°  →  {az_max:.4f}°  (span {az_max - az_min:.2f}°)")
    print(f"\tAltitude: {alt_min:.4f}°  →  {alt_max:.4f}°  (span {alt_max - alt_min:.2f}°)")   

def sample_year_positions(lat: float, lon: float, year: int, step_minutes: int = 1):
    """Sun position at every `step_minutes` interval over one year, above ALT_MIN."""
    start = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(year+1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    step = timedelta(minutes=step_minutes)

    # Table: datetime string: az, alt
    sun_position_table: dict[str, tuple[float, float]] = {}

    current = start
    while current < end:
        alt, az = get_sun_position(current, lon, lat)

        # Only saving for sun above horizon
        if alt >= ALT_MIN:
            sun_position_table[current.strftime(("%Y-%m-%d %H:%M"))] = (round(az, 4), round(alt, 4))
        
        current += step

    total_minutes = 365*24*60
    above_horizon_minutes = len(sun_position_table)

    print(f"\nTotal minutes in 2026: {total_minutes:,}")
    print(f"Above-horizon minutes: {above_horizon_minutes:,}  ({above_horizon_minutes/total_minutes*100:.1f}%)")

    calculate_min_max_range(sun_position_table)
    return sun_position_table


def build_sun_position_grid(
    lat: float = LAT,
    lon: float = LON,
    year: int = YEAR,
    output_path=SUN_POSITION_GRID_PATH,
) -> list[tuple[int, int]]:
    # Create a dict to store 1°/1° grid sun position table
    # Key: azimuth and altitude rounded to nearest 1°
    # Value: list of all pairs (az, alt) that fall in this range
    positions = sample_year_positions(lat, lon, year)
    grid_sun_position_table: dict[tuple[int, int], list[tuple[float, float, str]]] = defaultdict(list)

    for datetime_str, (az, alt) in positions.items():
        grid_key = (round(az), round(alt))
        grid_sun_position_table[grid_key].append((az, alt, datetime_str))

    n_cells = len(grid_sun_position_table)
    print(f"\nNumber of cells: {n_cells}")

    list_grid_pos = list(grid_sun_position_table.keys())
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "wb") as f:
        pickle.dump(list_grid_pos, f)

    return list_grid_pos

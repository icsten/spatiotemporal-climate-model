"""
Precompute a building shadow map for every (azimuth, altitude) pair that
occurs above the horizon over a year (see sun_position.build_sun_position_grid),
for a fixed area of interest.
"""

import pickle
 
import geopandas as gpd
 
from config import BUILDINGS_PATH, PRECOMPUTED_SHADOWS_DIR, SUN_POSITION_GRID_PATH
from shadow_geometry import calculate_shadow

def precompute_shadows(buildings: gpd.GeoDataFrame, sun_positions: list[tuple[int, int]]):
    PRECOMPUTED_SHADOWS_DIR.mkdir(parents=True, exist_ok=True)
 
    for az, alt in sun_positions:
        output_path = PRECOMPUTED_SHADOWS_DIR / f"shadow_az_{az}_alt_{alt}.parquet"
        if output_path.exists():    # if file exist already, it doesnt compute again -> TODO: check the bbox coverage requested and already computed
            continue
 
        shadows = calculate_shadow(buildings, az, alt, id_col="building_id")
        shadows.to_parquet(output_path, compression="snappy", index=False)
        print(f"Shadow computed for azimuth {az}° and altitude {alt}°.")

if __name__ == "__main__":
    print("Loading Buildings ...")
    buildings = gpd.read_file(BUILDINGS_PATH)
    print(f"\t{len(buildings)} buildings loaded, CRS: {buildings.crs}")

    print("Loading Sun Position List ...")
    with open(SUN_POSITION_GRID_PATH, "rb") as f:
        list_sun_pos = pickle.load(f)
    
    print(f"\t{len(list_sun_pos)} sun positios to compute")

    precompute_shadows(buildings, list_sun_pos)

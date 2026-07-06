from shapely.geometry import Polygon
from shapely import polygons as shapely_polygons, unary_union
from pathlib import Path

import geopandas as gpd
import numpy as np

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pickle

# ------------- CONFIG ---------------
OUTPUT_FOLDER = Path("./precomputed_shadows")
BUILDINGS_PATH = "./data/buildings_campus_sp_simplified.fgb"
SUN_POSITION_PATH = "./data/grid_sun_pos.pkl"

LAT        = 52.13896498167249
_lat_rad   = np.radians(LAT)
_M_PER_DEG_LON = 111320 * np.cos(_lat_rad)
_M_PER_DEG_LAT = 110540
# ------------------------------------

def _project_shadow_vectorized(coords, height, ox, oy):
    """
    Build shadow polygon for one building using fully vectorized numpy ops.
    coords : (n, 2) array of exterior ring vertices (closing vertex dropped)
    ox, oy : offset per metre of height, already in degrees
    Returns a Shapely Polygon.
    """
    offset = np.array([ox * height, oy * height])
    shifted = coords + offset

    n = len(coords)
    i = np.arange(n)
    j = (i + 1) % n

    # Each quad: 4 corners × n quads × 2 coords → shape (n, 4, 2)
    quads_coords = np.stack([
        coords[i],    # v_i
        coords[j],    # v_i+1
        shifted[j],   # shifted v_i+1
        shifted[i],   # shifted v_i
    ], axis=1)        # (n, 4, 2)

    # Build all n quads in one call - no Python loop
    quads = shapely_polygons(quads_coords)

    shadow = unary_union([Polygon(coords), Polygon(shifted), *quads])
    return shadow

def calculate_shadow(buildings, az_deg, alt_deg):
    scale = 1.0 / np.tan(np.radians(alt_deg))
    dx_per_m = -np.sin(np.radians(az_deg)) * scale / _M_PER_DEG_LON
    dy_per_m = -np.cos(np.radians(az_deg)) * scale / _M_PER_DEG_LAT

    shadows = []
    for row in buildings.itertuples():
        shadow = _project_shadow_vectorized(
            np.array(row.geometry.exterior.coords[:-1]),
            row.height,
            dx_per_m,
            dy_per_m,
        )
        shadows.append({
            "original_building_id": row.original_building_id,
            "height": row.height,
            "geometry": shadow,
        })
    
    shadows = dissolve_shadows_building_id(gpd.GeoDataFrame(shadows, crs=buildings.crs))
    return shadows

def dissolve_shadows_building_id(shadows):
    gdf = shadows.dissolve(by="original_building_id", aggfunc={"height": "first"})
    gdf.index.name = "building_id"
    gdf = gdf.reset_index()
    return gdf

def save_shadow_as_file(shadow, output_file_path):
    shadow.to_parquet(output_file_path, compression="snappy", index=False)

def precompute_shadows(buildings, sun_position):
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    for az, alt in list_sun_pos:
        output_file_path = OUTPUT_FOLDER / f"shadow_az_{az}_alt_{alt}.parquet"

        if output_file_path.exists():
            continue

        shadows = calculate_shadow(buildings, az, alt)
        save_shadow_as_file(shadows, output_file_path)
        print(f"Shadow computed for Azimuth {az}° and Altitude {alt}°.")

if __name__ == "__main__":
    # Load buildings and sun position list
    print("Loading Buildings ...")
    buildings = gpd.read_file(BUILDINGS_PATH)
    print(f"\t{len(buildings)} buildings loaded, CRS: {buildings.crs}")

    print("Loading Sun Position List ...")
    with open(SUN_POSITION_PATH, "rb") as f:
        list_sun_pos = pickle.load(f)
    
    print(f"\t{len(list_sun_pos)} sun positios to compute")

    precompute_shadows(buildings, list_sun_pos)

    

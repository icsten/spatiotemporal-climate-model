import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon
from shapely import polygons as shapely_polygons, unary_union
 
from config import LAT
 
_LAT_RAD = np.radians(LAT)
_M_PER_DEG_LON = 111320 * np.cos(_LAT_RAD)
_M_PER_DEG_LAT = 110540

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

def calculate_shadow(features: gpd.GeoDataFrame, az_deg: float, alt_deg: float, id_col: str) -> gpd.GeoDataFrame:
    """
    Project shadows for every feature in features for a given sun position.
 
    Parameters:
        features: GeoDataFrame with columns [id_col, "height", "geometry"].
                  Works identically for buildings or trees.
        az_deg, alt_deg: sun position, in degrees.
        id_col: name of the identifier column to dissolve shadow pieces by
                (a feature may be split across multiple polygon parts that
                must be reunited into a single shadow).
 
    Returns a GeoDataFrame with columns [id_col, "height", "geometry"],
    one dissolved shadow polygon per feature.
    """
    if features.empty:
        return gpd.GeoDataFrame(columns=[id_col, "height", "geometry"], geometry="geometry", crs=features.crs)
 
    scale = 1.0 / np.tan(np.radians(alt_deg))
    dx_per_m = -np.sin(np.radians(az_deg)) * scale / _M_PER_DEG_LON
    dy_per_m = -np.cos(np.radians(az_deg)) * scale / _M_PER_DEG_LAT
 
    rows = []
    for row in features.itertuples():
        shadow = _project_shadow_vectorized(
            np.array(row.geometry.exterior.coords[:-1]),
            row.height,
            dx_per_m,
            dy_per_m,
        )
        rows.append({id_col: getattr(row, id_col), "height": row.height, "geometry": shadow})
 
    shadows = gpd.GeoDataFrame(rows, crs=features.crs)
    return _dissolve_by_id(shadows, id_col)
 
 
def _dissolve_by_id(shadows: gpd.GeoDataFrame, id_col: str) -> gpd.GeoDataFrame:
    """Merge shadow pieces that belong to the same feature id into one polygon."""
    gdf = shadows.dissolve(by=id_col, aggfunc={"height": "first"})
    gdf.index.name = "building_id"
    gdf = gdf.reset_index()
    return gdf


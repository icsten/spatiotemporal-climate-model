from pathlib import Path

# Coordinates Magdeburg and reference year
LAT = 52.13896498167249
LON = 11.645601397328756
YEAR = 2026

# Sun altitudes below this (degrees) are not computed: too low in the horizon
ALT_MIN = 2

# Coordinate reference systems
SOURCE_CRS = "EPSG:4326"        # lon/lat, used for all stored geometry files
LOCAL_METRIC_CRS = "EPSG:25832" # ETRS89 / UTM 32N, used for length/area math

# Data paths
DATA_DIR = Path("./data")
PRECOMPUTED_SHADOWS_DIR = Path("./precomputed_shadows")
BUILDINGS_PATH = DATA_DIR / "buildings_geometry.fgb"
ORIGINAL_BUILDINGS_PATH = DATA_DIR / "buildings_geometry_original.fgb"
TREES_PATH = DATA_DIR / "trees_geometry.fgb"
ORIGINAL_TREES_PATH = DATA_DIR / "trees_geometry_original.fgb"
MERGED_BUILDINGS_AND_TREES_PATH = DATA_DIR / "merged_buildings_and_trees.fgb"


# Pickled list of (azimuth, altitude) pairs that actually occur above 
# the horizon over one year at (LAT, LON). This is the set of
# precomputed shadow maps; see sun_position.py.
SUN_POSITION_GRID_PATH = DATA_DIR / "grid_sun_pos.pkl"

# Routing defaults
WALK_SPEED_KPH_DEFAULT = 5.0
EDGE_BBOX_BUFFER_M = 50
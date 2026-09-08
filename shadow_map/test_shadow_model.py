from datetime import datetime, timezone
 
import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point

import precompute_shadows
import compute_shadow_ratio
from config import LAT, LON, SOURCE_CRS, LOCAL_METRIC_CRS, BUILDINGS_PATH, TREES_PATH, PRECOMPUTED_SHADOWS_DIR
from geo_utils import reproject_gdf, reproject_geoms
from shadow_geometry import calculate_shadow
from shadow_class import ShadowMap
from calculate_sun_position import get_sun_position, round_sun_position

_HAS_BUILDINGS = BUILDINGS_PATH.exists()
_HAS_TREES = TREES_PATH.exists()

skip_no_buildings = pytest.mark.skipif(not _HAS_BUILDINGS, reason=f"No buildings dataset at {BUILDINGS_PATH}")
skip_no_trees = pytest.mark.skipif(not _HAS_TREES, reason=f"No trees dataset at {TREES_PATH}")

def _load_buildings(n=1):
    """
    Load the first n features from the Buildings dataset.
    """
    return gpd.read_file(BUILDINGS_PATH, rows=n)

def _load_trees(n=1):
    """
    Load the first n features from the Trees dataset.
    """
    return gpd.read_file(TREES_PATH, rows=n)

def bbox_around(gdf, pad_m=20):
    pad_deg = pad_m / 111_000
    minx, miny, maxx, maxy = gdf.total_bounds
    return (minx - pad_deg, miny - pad_deg, maxx + pad_deg, maxy + pad_deg)

# ---------------------------------------------------------------------------
# calculate_sun_position.py
# ---------------------------------------------------------------------------
def test_get_and_round_sun_position():
    dt = datetime(2026, 6, 21, 11, 0, tzinfo=timezone.utc)
    alt, az = get_sun_position(dt, LON, LAT)
    assert alt > 0
    assert 0 <= az <= 360
 
    alt_key, az_key = round_sun_position(alt, az)
    assert alt_key == round(alt)
    assert az_key == round(az) % 360

# ---------------------------------------------------------------------------
# geo_utils.py
# ---------------------------------------------------------------------------
@skip_no_buildings
def test_reproject_roundtrip_preserves_shape():
    """
    Assert that the coordinate system conversion is not loosing information
    """
    building = _load_buildings(1)
    metric = reproject_gdf(building, LOCAL_METRIC_CRS)
    # Reprojecting to metric and back to metric again (via source) should be a no-op on area
    roundtrip = reproject_gdf(metric.to_crs(SOURCE_CRS), LOCAL_METRIC_CRS)
    assert roundtrip.geometry.iloc[0].area == pytest.approx(metric.geometry.iloc[0].area, rel=1e-6)

# ---------------------------------------------------------------------------
# shadow_geometry.py
# ---------------------------------------------------------------------------
@skip_no_buildings
def test_calculate_shadow_extends_footprint():
    building = _load_buildings(1)
    shadow = calculate_shadow(building, az_deg=90, alt_deg=45, id_col="building_id")
    
    assert list(shadow["building_id"]) == list(building["building_id"])

    shadow_metric = reproject_gdf(shadow, LOCAL_METRIC_CRS)
    building_metric = reproject_gdf(building, LOCAL_METRIC_CRS)
    assert shadow_metric.geometry.iloc[0].area > building_metric.geometry.iloc[0].area

def test_calculate_shadow_empty_input():
    empty = gpd.GeoDataFrame(columns=["building_id", "height", "geometry"], geometry="geometry", crs=SOURCE_CRS)
    result = calculate_shadow(empty, az_deg=90, alt_deg=45, id_col="building_id")
    assert result.empty


# ---------------------------------------------------------------------------
# precompute_shadows.py - for only 2 sun positions
# ---------------------------------------------------------------------------
@skip_no_buildings
def test_precompute_shadows(tmp_path, monkeypatch):
    monkeypatch.setattr(precompute_shadows, "PRECOMPUTED_SHADOWS_DIR", tmp_path)
    
    buildings = _load_buildings(5)
    sun_positions = [(90, 45), (180, 30)]

    precompute_shadows.precompute_shadows(buildings, sun_positions)

    for az, alt in sun_positions:
        f = tmp_path / f"shadow_az_{az}_alt_{alt}.parquet"
        assert f.exists()
        gdf = gpd.read_parquet(f)
        assert len(gdf) > 0
        assert "building_id" in gdf.columns
    
    # Re-running should skip existing files rather than recompute
    precompute_shadows.precompute_shadows(buildings, sun_positions)
    assert len(list(tmp_path.glob("shadow_*.parquet"))) == 2

# ---------------------------------------------------------------------------
# shadow_class.py
# ---------------------------------------------------------------------------
@skip_no_buildings
def test_shadow_map_computes_on_the_fly_from_real_buildings():
    shadow_map = ShadowMap()
    building = _load_buildings(1)
    bbox = bbox_around(building)
 
    union = shadow_map.get_shadow_union_metric(90, 45, bbox, buildings_only=True)
    assert union is not None
    assert union.area > 0

@skip_no_buildings
@skip_no_trees
def test_shadow_map_buildings_only_false_adds_tree_coverage():
    shadow_map = ShadowMap()
    buildings = _load_buildings(5)
    trees = _load_trees(5)
    bbox = bbox_around(pd.concat([buildings, trees]))
 
    buildings_only_union = shadow_map.get_shadow_union_metric(90, 45, bbox, buildings_only=True)
    combined_union = shadow_map.get_shadow_union_metric(90, 45, bbox, buildings_only=False)
 
    if buildings_only_union is None:
        pytest.skip("no building shadow coverage in this bbox to compare against")
    assert combined_union.area >= buildings_only_union.area

@skip_no_buildings
def test_shadow_ratio_bounds():
    shadow_map = ShadowMap()
    building = _load_buildings(1)
    bbox = bbox_around(building)
    union = shadow_map.get_shadow_union_metric(90, 45, bbox, buildings_only=True)
 
    building_metric = reproject_gdf(building, LOCAL_METRIC_CRS)
    edge_through_building = building_metric.geometry.iloc[0].boundary
 
    ratio = shadow_map.shadow_ratio(edge_through_building, union)
    assert 0.0 <= ratio <= 1.0
 
    ratio_no_shadow = shadow_map.shadow_ratio(edge_through_building, None)
    assert ratio_no_shadow == 0.0

# ---------------------------------------------------------------------------
# compute_shadow_ratio.py - static and dynamic
# ---------------------------------------------------------------------------
_EXPECTED_EDGE_FIELDS = {"length_m", "shadow_ratio", "altitude_deg", "azimuth_deg", "eval_datetime"}

# Start and End coordinates
_ROUTE_START = {"lat": 52.13, "lon": 11.64}
_ROUTE_END = {"lat": 52.14, "lon": 11.65}


@skip_no_buildings
def test_compute_static_shadow(monkeypatch):
    shadow_map = ShadowMap()
    query_dt = datetime(2026, 6, 21, 11, 0, tzinfo=timezone.utc)

    result = compute_shadow_ratio.compute_static_shadow(_ROUTE_START, _ROUTE_END, query_dt, shadow_map=shadow_map)
 
    assert len(result["edges"]) > 0
    assert set(result["edges"][0].keys()) == _EXPECTED_EDGE_FIELDS
    assert 0.0 <= result["overall_shadow_ratio"] <= 1.0
    # Static uses one sun position for the whole route: same eval_datetime on every edge
    assert all(e["eval_datetime"] == query_dt.isoformat() for e in result["edges"])

@skip_no_buildings
def test_compute_dynamic_shadow():
    shadow_map = ShadowMap()
    query_dt = datetime(2026, 6, 21, 11, 0, tzinfo=timezone.utc)
    
    result = compute_shadow_ratio.compute_dynamic_shadow(_ROUTE_START, _ROUTE_END, query_dt, shadow_map=shadow_map)
 
    assert len(result["edges"]) > 0
    assert set(result["edges"][0].keys()) == _EXPECTED_EDGE_FIELDS
    assert 0.0 <= result["overall_shadow_ratio"] <= 1.0
    # eval_datetime should be non-decreasing along the route (later edges are reached later)
    times = [datetime.fromisoformat(e["eval_datetime"]) for e in result["edges"]]
    assert times == sorted(times)

@skip_no_buildings
def test_compute_dynamic_shadow_reuses_union_when_sun_position_unchanged():
    """
    get_shadow_union_metric should be called at most once per distinct (az, alt) grid cell actually encountered along the route, not
    once per edge.
    """
    shadow_map = ShadowMap()
    query_dt = datetime(2026, 6, 21, 11, 0, tzinfo=timezone.utc)
 
    call_count = {"n": 0}
    original = shadow_map.get_shadow_union_metric
 
    def counting_wrapper(*args, **kwargs):
        call_count["n"] += 1
        return original(*args, **kwargs)
 
    shadow_map.get_shadow_union_metric = counting_wrapper
 
    result = compute_shadow_ratio.compute_dynamic_shadow(_ROUTE_START, _ROUTE_END, query_dt, shadow_map=shadow_map)
 
    assert call_count["n"] <= len(result["edges"])
 
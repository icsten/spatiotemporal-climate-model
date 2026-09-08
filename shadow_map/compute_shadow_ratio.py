from datetime import datetime, timedelta, timezone
from typing import List, Optional
 
from shapely.ops import substring
 
from geo_utils import reproject_geoms
from osm_routing import get_route_edges
from shadow_class import ShadowMap
from calculate_sun_position import get_sun_position, round_sun_position
from config import ALT_MIN, EDGE_BBOX_BUFFER_M, SOURCE_CRS, LOCAL_METRIC_CRS
 
 
def compute_static_shadow(start, end, query_datetime, network_type="walk", shadow_map=None, buildings_only=True) -> dict:
    """
    Calculates shadow ratio for the whole route using one sun position (query datetime).
    """
    shadow_map = shadow_map or ShadowMap()
    query_datetime = _ensure_utc(query_datetime)
 
    altitude, azimuth = get_sun_position(query_datetime, start["lon"], start["lat"])
    if altitude < ALT_MIN:
        raise ValueError(f"sun altitude {altitude:.2f}° is below the minimum {ALT_MIN}°")
    alt_key, az_key = round_sun_position(altitude, azimuth)
 
    _, edges = get_route_edges(start["lat"], start["lon"], end["lat"], end["lon"], network_type)
    if not edges:
        raise ValueError("No route found between the given coordinates")
 
    bbox = _bbox_from_edges(edges)
    edge_geoms_metric = reproject_geoms([e["geometry"] for e in edges])
 
    # One shadow union for the whole route -> reused for every edge
    union_metric = shadow_map.get_shadow_union_metric(az_key, alt_key, bbox, buildings_only)
 
    edge_results = []
    total_len, total_shadow_len = 0.0, 0.0
 
    for e, geom_metric in zip(edges, edge_geoms_metric):
        ratio = shadow_map.shadow_ratio(geom_metric, union_metric)
        edge_results.append({
            "length_m": e["length_m"],
            "shadow_ratio": ratio,
            "altitude_deg": altitude,
            "azimuth_deg": azimuth,
            "eval_datetime": query_datetime.isoformat(),
        })
        total_len += e["length_m"]
        total_shadow_len += ratio * e["length_m"]
 
    return {
        "total_length_m": total_len,
        "overall_shadow_ratio": (total_shadow_len / total_len if total_len else 0.0),
        "edges": edge_results,
    }
 
 
def compute_dynamic_shadow(start, end, query_datetime, network_type="walk", shadow_map=None, buildings_only=True) -> dict:
    """
    Evaluated at each edge's own arrival time (query_datetime + cumulative travel time of preceding edges).
    """
    shadow_map = shadow_map or ShadowMap()
    query_datetime = _ensure_utc(query_datetime)

    _, edges = get_route_edges(start["lat"], start["lon"], end["lat"], end["lon"], network_type)
    if not edges:
        raise ValueError("No route found between the given coordinates")
 
    cumulative_s = 0.0
    edge_results = []
    total_len, total_shadow_len = 0.0, 0.0

    previous_sun_key = None
    previous_union_metric = None
 
    for e in edges:
        geom = e["geometry"]
        eval_time = query_datetime + timedelta(seconds=cumulative_s)
        mid = geom.interpolate(0.5, normalized=True)
        altitude, azimuth = get_sun_position(eval_time, mid.x, mid.y)
 
        ratio = 0.0
        if altitude >= ALT_MIN:
            alt_key, az_key = round_sun_position(altitude, azimuth)
            sun_key = (az_key, alt_key)

            if sun_key != previous_sun_key:
                bbox = _bbox_with_buffer(geom, EDGE_BBOX_BUFFER_M)     # buffer set to 50m
                previous_union_metric = shadow_map.get_shadow_union_metric(az_key, alt_key, bbox, buildings_only)
                previous_sun_key = sun_key
            
            geom_metric = reproject_geoms([geom])[0]
            ratio = shadow_map.shadow_ratio(geom_metric, previous_union_metric)
 
        edge_results.append({
            "length_m": e["length_m"],
            "shadow_ratio": ratio,
            "altitude_deg": altitude,
            "azimuth_deg": azimuth,
            "eval_datetime": eval_time.isoformat(),
        })
        total_len += e["length_m"]
        total_shadow_len += ratio * e["length_m"]
        cumulative_s += e["travel_time_s"]
 
    return {
        "total_length_m": total_len,
        "overall_shadow_ratio": (total_shadow_len / total_len if total_len else 0.0),
        "edges": edge_results,
    }


def _ensure_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _bbox_from_edges(edges: List[dict]):
    xs = [c[0] for e in edges for c in e["geometry"].coords]
    ys = [c[1] for e in edges for c in e["geometry"].coords]
    return (min(xs), min(ys), max(xs), max(ys))


def _bbox_with_buffer(geom, buffer_m: float):
    """
    Bounding box around geom, padded by buffer_m.
    """
    geom_metric = reproject_geoms([geom], source_crs=SOURCE_CRS, target_crs=LOCAL_METRIC_CRS)[0]
    buffered_metric = geom_metric.buffer(buffer_m)
    buffered_source = reproject_geoms([buffered_metric], source_crs=LOCAL_METRIC_CRS, target_crs=SOURCE_CRS)[0]
    return buffered_source.bounds
import os
 
import geopandas as gpd
import pandas as pd

from shapely.geometry import box
from typing import Tuple
 
from config import BUILDINGS_PATH, TREES_PATH, PRECOMPUTED_SHADOWS_DIR, LOCAL_METRIC_CRS, SOURCE_CRS
from geo_utils import reproject_gdf, reproject_geoms
from shadow_geometry import calculate_shadow

class MissingShadowFileError(Exception):
    pass

class ShadowMap:
    def __init__(
        self,
        shadow_dir=PRECOMPUTED_SHADOWS_DIR,
        buildings_path=BUILDINGS_PATH,
        trees_path=TREES_PATH,
        metric_crs=LOCAL_METRIC_CRS,
        source_crs=SOURCE_CRS,
    ):
        self.shadow_dir = shadow_dir
        self.buildings_path = buildings_path
        self.trees_path = trees_path
        self.metric_crs = metric_crs
        self.source_crs = source_crs
 
        self._cache: dict = {}  # (az_key, alt_key, bbox, buildings_only) -> metric union geometry


    def get_shadow_union_metric(
        self,
        az_key: int,
        alt_key: int,
        bbox: Tuple[float, float, float, float],
        buildings_only: bool = True,    # Considers only geometry of buildings, no trees
    ):
        """
        Return a single shapely geometry: all shadow coverage for a given bbox,
        at sun position (az_key, alt_key).
        Returns None if there is no shadow coverage at all.
        """
        cache_key = (az_key, alt_key, bbox, buildings_only)
        if cache_key in self._cache:
            return self._cache[cache_key]
 
        building_shadows = self._get_building_shadows_metric(az_key, alt_key, bbox)
        pieces = [building_shadows] if building_shadows is not None else []
 
        if not buildings_only:
            tree_shadows = self._get_tree_shadows_metric(az_key, alt_key, bbox)
            if tree_shadows is not None:
                pieces.append(tree_shadows)
 
        union = self._union_within_bbox(pieces, bbox)
        self._cache[cache_key] = union
        return union
 

    def shadow_ratio(self, edge_geom_metric, union_metric) -> float:
        """Return total shadow ratio for a edge/route."""
        total_len = edge_geom_metric.length
        if total_len == 0 or union_metric is None:
            return 0.0
        return edge_geom_metric.intersection(union_metric).length / total_len
    

    def _get_building_shadows_metric(self, az_key: int, alt_key: int, bbox: Tuple[float, float, float, float], id_col="building_id"):
        """Precomputed file if it covers bbox, else compute on the fly from BUILDINGS_PATH."""
        path = self._precomputed_path(az_key, alt_key)
        shadows = None
 
        if os.path.exists(path):
            precomputed = gpd.read_parquet(path)
            if not precomputed.empty and box(*precomputed.total_bounds).contains(box(*bbox)):
                shadows = precomputed
 
        if shadows is None:
            buildings = gpd.read_file(self.buildings_path, bbox=bbox)
            shadows = calculate_shadow(buildings, az_key, alt_key, id_col=id_col)
 
        if shadows.empty:
            return None
        return reproject_gdf(shadows, self.metric_crs)
 

    def _precomputed_path(self, az_key: int, alt_key: int) -> str:
        return os.path.join(self.shadow_dir, f"shadow_az_{az_key}_alt_{alt_key}.parquet")
 
 
    def _get_tree_shadows_metric(self, az_key: int, alt_key: int, bbox: Tuple[float, float, float, float]):
        """Trees are not precomputed -> always compute on the fly from TREES_PATH."""
        trees = gpd.read_file(self.trees_path, bbox=bbox)
        if trees.empty:
            return None
        shadows = calculate_shadow(trees, az_key, alt_key, id_col="tree_id")
        if shadows.empty:
            return None
        return reproject_gdf(shadows, self.metric_crs)
 
 
    def _union_within_bbox(self, shadow_gdfs, bbox: Tuple[float, float, float, float]):
        if not shadow_gdfs:
            return None
 
        bbox_metric = reproject_geoms([box(*bbox)], target_crs=self.metric_crs)[0]
 
        candidates = []
        for gdf in shadow_gdfs:
            idx = list(gdf.sindex.query(bbox_metric, predicate="intersects"))
            if idx:
                candidates.append(gdf.iloc[idx].geometry)
 
        if not candidates:
            return None
 
        return pd.concat(candidates).union_all()

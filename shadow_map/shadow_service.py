import pybdshadow
import geopandas as gpd
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

BUILDINGS_PATH = "./data/buildings.fgb"


class ShadowService:
    def __init__(self, bbox, buildings_path=BUILDINGS_PATH):
        self.buildings = self.get_building_from_bbox(bbox, buildings_path)
        self.shadows_dict: dict[str, gpd.GeoDataFrame] = {}

    def get_building_from_bbox(self, bbox, buildings_path):
        min_lon, min_lat, max_lon, max_lat = bbox
        buildings = gpd.read_file(buildings_path, bbox=bbox)
        buildings_processed = pybdshadow.bd_preprocess(buildings, height="height")
        return buildings_processed

    def get_shadows(self, dt: pd.Timestamp) -> gpd.GeoDataFrame:
        rounded_dt = dt.replace(minute=(dt.minute // 10)*10, second=0, microsecond=0)
        key = rounded_dt.isoformat()

        if key not in self.shadows_dict:
            shadows = self._calculate_shadow(rounded_dt)
            self.shadows_dict[key] = shadows
        return self.shadows_dict[key]

    def _calculate_shadow(self, dt, roof=False, include_building=True, crs=4326):        
        shadows = pybdshadow.bdshadow_sunlight(
            self.buildings,
            date=dt,
            height="height",
            roof=roof,
            include_building=include_building,
        ) 
        shadows = shadows.set_crs(crs)
        return shadows

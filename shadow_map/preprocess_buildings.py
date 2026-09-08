"""
Build the buildings source dataset (BUILDINGS_PATH, buildings_geometry.fgb)
from raw CityGML (.gml) building files. Buildings are preprocessed before use.

Source data: Sachsen-Anhalt Geodatenportal (LVermGeo)
https://www.lvermgeo.sachsen-anhalt.de/de/gdp-geodaten-karten.html
 
Output schema: building_id, height, geometry (EPSG:4326), one polygon per
building. Buildings originally split into multiple height-differentiated
parts are grouped and dissolved (see group_buildings_from_height).
"""

import os
 
from lxml import etree
from shapely.geometry import Polygon
import pandas as pd
import geopandas as gpd
 
from config import BUILDINGS_PATH, SOURCE_CRS, LOCAL_METRIC_CRS, ORIGINAL_BUILDINGS_PATH

NS = {
    "bldg": "http://www.opengis.net/citygml/building/1.0",
    "gml":  "http://www.opengis.net/gml",
}

def build_buildings_dataset(input_folder: str, output_path=BUILDINGS_PATH):
    '''
    # Commented because the original buildings file is already in .fgb format

    parsed = [
        extract_building_information(os.path.join(input_folder, f))
        for f in os.listdir(input_folder)
        if f.endswith(".gml")
    ]
    parsed = [gdf for gdf in parsed if gdf is not None and not gdf.empty]
    if not parsed:
        print("No building information extracted from any file.")
        return
    '''
 
    #merged = gpd.GeoDataFrame(pd.concat(parsed, ignore_index=True), crs=_SOURCE_CRS_GML)
    buildings = gpd.read_file(ORIGINAL_BUILDINGS_PATH)
    merged = group_buildings_from_height(buildings)
    merged = merged[["building_id", "height", "geometry"]].to_crs(SOURCE_CRS)
 
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_file(output_path, driver="FlatGeobuf")
    print(f"Saved {len(merged)} buildings to {output_path}")
 
 
def extract_building_information(file_path):
    root = etree.parse(file_path).getroot()
    building_ids, heights, geometries = [], [], []
 
    for building in root.findall(".//bldg:Building", NS):
        building_id = building.get("{http://www.opengis.net/gml}id")
        parts = building.findall(".//bldg:BuildingPart", NS) or [building]
 
        for part in parts:
            h_el = part.find(".//bldg:measuredHeight", NS)
            height = float(h_el.text.strip()) if h_el is not None else None
 
            for pos_el in part.findall(".//gml:posList", NS):
                vals = list(map(float, pos_el.text.split()))
                coords = [(vals[i], vals[i + 1]) for i in range(0, len(vals), 3)]
                if len(coords) < 3:
                    continue
                poly = Polygon(coords)
                if not poly.is_valid or poly.area <= 0:
                    continue
                building_ids.append(building_id)
                heights.append(height)
                geometries.append(poly)
 
    return gpd.GeoDataFrame({"building_id": building_ids, "height": heights}, geometry=geometries, crs=_SOURCE_CRS_GML)
 
 
def group_buildings_from_height(gdf):
    """
    1. Round building height to the nearest 0.5m.
    2. Dissolve polygons sharing the same building ID and rounded height.
    3. Assign a fresh, unique building_id per resulting polygon.
    """
    gdf = gdf.copy()
    gdf["height"] = (gdf["height"] / 0.5).round() * 0.5
 
    grouped = (
        gdf.groupby(["building_id", "height"], as_index=False)
        .agg(geometry=("geometry", lambda x: x.union_all()))
    )
    grouped = (
        gpd.GeoDataFrame(grouped, geometry="geometry", crs=gdf.crs)
        .explode(index_parts=False)
        .reset_index(drop=True)
    )
    grouped["building_id"] = range(len(grouped))
    return grouped
 
 
if __name__ == "__main__":
    build_buildings_dataset(input_folder=ORIGINAL_BUILDINGS_PATH)
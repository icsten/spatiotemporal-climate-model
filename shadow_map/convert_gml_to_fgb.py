from lxml import etree
from shapely.geometry import Polygon
import os
import pandas as pd
import geopandas as gpd

NS = {
    "bldg": "http://www.opengis.net/citygml/building/1.0",
    "gml":  "http://www.opengis.net/gml",
}

def read_gml_files(input_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)

    gdf_25832 = []

    for file in os.listdir(input_folder):
        if not file.endswith(".gml"):
            continue
        
        gml_path = os.path.join(input_folder, file)
        gdf = extract_building_information(gml_path)

        if gdf is None or gdf.empty:
            print(f"[skip] No building information extracted from file {gml_path}")
            continue
        
        # Create output filename
        base_name = os.path.splitext(file)[0]
        #output_path = os.path.join(output_folder, f"{base_name}.geojson", driver="GeoJSON")

        gdf_25832.append(gdf)

    if not gdf_25832:
        return [], []
    
    merged_gdf = gpd.GeoDataFrame(pd.concat(gdf_25832, ignore_index=True), crs=25832)
    merged_gdf = group_buildings_from_height(merged_gdf)
    
    # Save file with CRS 25832
    output_path_25832 = os.path.join(output_folder, "magdeburg_buildings_25832.fgb")
    merged_gdf.to_file(output_path_25832, driver="FlatGeobuf")
    print(f"Saved file {output_path_25832}")

    merged_gdf_4326 = merged_gdf.to_crs(4326)
    output_path_4326 = os.path.join(output_folder, "magdeburg_buildings_4326.fgb")
    merged_gdf_4326.to_file(output_path_4326, driver="FlatGeobuf")
    print(f"Saved file {output_path_4326}")


def extract_building_information(file_path):
    root = etree.parse(file_path).getroot()

    building_ids, part_ids, heights, geometries = [], [], [], []

    for building in root.findall(".//bldg:Building", NS):
        building_id = building.get("{http://www.opengis.net/gml}id")
        parts = building.findall(".//bldg:BuildingPart", NS) or [building]

        for part in parts:
            part_id = part.get("{http://www.opengis.net/gml}id")

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
                part_ids.append(part_id)
                heights.append(height)
                geometries.append(poly)

    return gpd.GeoDataFrame(
                {"building_id": building_ids, "part_id": part_ids, "height": heights},
                geometry=geometries,
                crs=25832,
            )

def group_buildings_from_height(gdf):
    '''
    1. Round building height to the nearest 0.5m.
    2. Dissolve polygons that share the same building ID and rounded height.
    '''
    gdf = gdf.copy()
    gdf["height"] = (gdf["height"] / 0.5).round() * 0.5

    gdf_grouped = (
        gdf
        .groupby(["building_id", "height"], as_index=False)
        .agg(geometry=("geometry", lambda x: x.union_all()))
    )

    # Convert to GeoDataFrame
    gdf_grouped = (
        gpd.GeoDataFrame(gdf_grouped, geometry="geometry", crs=gdf.crs)
        .explode(index_parts=False)
        .reset_index(drop=True)
    )

    gdf_grouped["original_building_id"] = gdf_grouped["building_id"]
    gdf_grouped["building_id"] = range(len(gdf_grouped))
    return gdf_grouped

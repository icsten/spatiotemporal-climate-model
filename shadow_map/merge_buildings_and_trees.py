import geopandas as gpd
import pandas as pd

from config import BUILDINGS_PATH, TREES_PATH, MERGED_BUILDINGS_AND_TREES_PATH

def merge_buildings_and_trees(buildings_path=BUILDINGS_PATH, trees_path=TREES_PATH, output_path=MERGED_BUILDINGS_AND_TREES_PATH):
    buildings = gpd.read_file(buildings_path).rename(columns={"building_id": "id"})
    trees = gpd.read_file(trees_path).rename(columns={"tree_id": "id"})
 
    merged = pd.concat([buildings, trees], ignore_index=True)
    merged = gpd.GeoDataFrame(merged, geometry="geometry", crs=buildings.crs)
    merged = merged[["id", "height", "geometry"]]
 
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_file(output_path)
    print(f"Saved {len(merged)} rows ({len(buildings)} buildings + {len(trees)} trees) to {output_path}")
 
if __name__ == "__main__":
    merge_buildings_and_trees()
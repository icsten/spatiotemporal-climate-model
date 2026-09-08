"""
Build the trees source dataset (TREES_PATH, trees_geometry.fgb) from the raw
tree inventory. Preprocessed before use.

Source data: Sachsen-Anhalt Geodatenportal (LVermGeo)
https://www.lvermgeo.sachsen-anhalt.de/de/gdp-geodaten-karten.html
Combines public and private tree records.

Raw records give each tree as a point with a trunk position, a crown
diameter ("Kronendurchmesser") and a height ("Baumhoehe"). This script
approximates each tree's canopy footprint as a circle (buffered point) using
the crown diameter, so it can go through the same shadow-projection code as
buildings.

Output schema: tree_id, height, geometry (EPSG:4326), one polygon per tree.
"""
import geopandas as gpd

from config import TREES_PATH, SOURCE_CRS, LOCAL_METRIC_CRS, ORIGINAL_TREES_PATH


def build_trees_dataset(original_tree_path: str = ORIGINAL_TREES_PATH, output_path=TREES_PATH):
    trees = gpd.read_file(original_tree_path)
    trees = trees.rename(columns={"Baumhoehe": "height", "baumnummer": "tree_id"})

    # Check na: if True -> dropna
    trees = trees.dropna(subset=["geometry", "Kronendurchmesser", "height"])

    # Approximate canopy as a circle around the trunk point
    crown_radius_m = trees["Kronendurchmesser"] / 2
    trees = gpd.GeoDataFrame(trees, geometry=trees["geometry"].buffer(crown_radius_m), crs=LOCAL_METRIC_CRS)

    # Check invalid geometry
    invalid = trees.geometry.apply(lambda g: g is None or g.is_empty)
    if invalid.any():
        trees = trees[~invalid]

    trees = trees.to_crs(SOURCE_CRS)
    trees = trees[["tree_id", "height", "geometry"]]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    trees.to_file(output_path, driver="FlatGeobuf")
    print(f"Saved {len(trees)} trees to {output_path}")


if __name__ == "__main__":
    build_trees_dataset()
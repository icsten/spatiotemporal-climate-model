import geopandas as gpd
from config import LOCAL_METRIC_CRS, SOURCE_CRS

def reproject_geoms(geoms, source_crs=SOURCE_CRS, target_crs=LOCAL_METRIC_CRS):
    """Reproject a list/iterable of shapely geometries. Returns a list."""
    gs = gpd.GeoSeries(list(geoms), crs=source_crs).to_crs(target_crs)
    return list(gs)


def reproject_gdf(gdf, target_crs=LOCAL_METRIC_CRS):
    """Reproject a GeoDataFrame, assuming SOURCE_CRS if it has none set."""
    if gdf.crs is None:
        gdf = gdf.set_crs(SOURCE_CRS)
    if str(gdf.crs) != target_crs:
        gdf = gdf.to_crs(target_crs)
    return gdf
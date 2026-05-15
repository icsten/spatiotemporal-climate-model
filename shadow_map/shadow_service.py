import pybdshadow
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

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

    def plot_shadows(
        self,
        dt,
        intersections=None,
        route_geom=None,
        save_path: str | None = None,
        buffer_factor: float = 0.4,
    ):
        fig, ax = plt.subplots(figsize=(12, 12))
        shadows = self.get_shadows(dt)

        # --- Split shadows ---
        ground_shadows = shadows[shadows["type"] == "ground"]
        roof_shadows   = shadows[shadows["type"] == "roof"]

        intersections_list = [gdf for gdf in intersections if gdf is not None and not gdf.empty]
        merged_intersections = pd.concat(intersections_list) if intersections_list else None

        # --- Plot shadows ---
        if len(ground_shadows) > 0:
            ground_shadows.plot(ax=ax, color="#555555", alpha=0.4)

        if len(roof_shadows) > 0:
            roof_shadows.plot(ax=ax, color="#cc0000", alpha=0.5)

        # --- Plot buildings ---
        self.buildings.plot(
            ax=ax,
            color="#3a86ff",
            alpha=0.8,
            edgecolor="white",
            linewidth=0.5,
        )

        # --- Plot route ---
        if route_geom is not None:
            gpd.GeoSeries(route_geom, crs=shadows.crs).plot(
                ax=ax,
                color="black",
                linewidth=2,
                linestyle="--",
                label="Route",
            )

        # --- Plot intersections ---
        if merged_intersections is not None and not merged_intersections.empty:
            merged_intersections.set_geometry("intersection").to_crs(epsg=4326).plot(
                            ax=ax,
                            color="yellow",
                            linewidth=4,
                            label="Shadow overlap",
                        )

        # --- Zoom to route area ---
        if route_geom is not None:
            all_bounds = [geom.bounds for geom in route_geom]
            minx = min(b[0] for b in all_bounds)
            miny = min(b[1] for b in all_bounds)
            maxx = max(b[2] for b in all_bounds)
            maxy = max(b[3] for b in all_bounds)

            x_buf = (maxx - minx) * buffer_factor
            y_buf = (maxy - miny) * buffer_factor
            ax.set_xlim(minx - x_buf, maxx + x_buf)
            ax.set_ylim(miny - y_buf, maxy + y_buf)

        # --- Legend ---
        legend_handles = [
            mpatches.Patch(color="#3a86ff", alpha=0.8, label="Buildings"),
            mpatches.Patch(color="#555555", alpha=0.4, label="Ground Shadow"),
        ]

        if len(roof_shadows) > 0:
            legend_handles.append(
                mpatches.Patch(color="#cc0000", alpha=0.5, label="Roof Shadow")
            )

        if merged_intersections is not None and not merged_intersections.empty:
            legend_handles.append(
                mpatches.Patch(color="yellow", label="Shadow overlap")
            )

        ax.legend(handles=legend_handles, loc="upper right")

        ax.set_title(f"Building Shadow {dt.strftime('%Y-%m-%d %H:%M')}", fontsize=14)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150)

        plt.show()
    

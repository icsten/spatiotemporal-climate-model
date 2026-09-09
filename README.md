# Spatiotemporal Environmental Framework for Urban Digital Twins

Part of the [IMIQ project](https://github.com/imiq-project/).

## 1. Overview

This project iniatilly develops a spatiotemporal framework that provides environmental data to an urban digital twin (DT). It is under active development and currently consists of two independent components:

1. **Shadow Model** (`shadow_map/`) — computes where shadows fall over time, and the proportion of shadow coverage along a given route.
2. **Thermal Comfort** (`thermal_comfort/`) — estimates outdoor thermal comfort (UTCI) from meteorological inputs.

These components are intended to support the following applications:

- A shadow map layer for visualization in a digital twin dashboard.
- Shadow-ratio-aware personalized route recommendations for pedestrians and cyclists.
- Heat-aware navigation input for autonomous systems.

The two components are independent at present, each with its own code and `requirements.txt`. They are documented separately in the sections below.

---

## 2. Shadow Model (`shadow_map/`)

### 2.1 Project layout

```
spatiotemporal-climate-model/
└── shadow_map/
    ├── data/
    │   ├── buildings_geometry_original.fgb       raw building source (before preprocessing)
    │   ├── buildings_campus_sp_simplified.fgb    simplified buildings, for bulk shadow precomputation only
    │   ├── buildings_geometry.fgb                processed buildings (used at request time)
    │   ├── trees_geometry_original.fgb           raw tree source (before preprocessing)
    │   ├── trees_geometry.fgb                    processed trees (used at request time)
    │   ├── merged_buildings_and_trees.fgb        archival combination of the two processed datasets
    │   └── grid_sun_pos.pkl                      precomputed sun-position grid
    ├── calculate_sun_position.py
    ├── compute_shadow_ratio.py
    ├── config.py
    ├── create_shadow_slide_visualization.py
    ├── example_shadow_ratio.py
    ├── geo_utils.py
    ├── merge_buildings_and_trees.py
    ├── osm_routing.py
    ├── precompute_shadows.py
    ├── preprocess_buildings.py
    ├── preprocess_trees.py
    ├── shadow_class.py
    ├── shadow_geometry.py
    ├── test_shadow_model.py
    └── requirements.txt
```

All modules are flat files in a single directory, with no
package/`__init__.py` structure; they import one another directly by name,
e.g. `from config import ...`. This means every script and test in
`shadow_map/` should be run with `shadow_map/` as the working directory
(or with that directory on `PYTHONPATH`), so that these imports resolve.
 
`precompute_shadows.py` writes its output to a `precomputed_shadows/`
directory, generated at runtime alongside `data/` (i.e., a sibling of
`data/`, not nested inside it — see `PRECOMPUTED_SHADOWS_DIR` in
`config.py`). It is not listed above because it is generated output rather
than checked-in source.
 
`preprocess_buildings.py` and `preprocess_trees.py` consume raw upstream
inputs — a folder of CityGML files (`RAW_GML_DIR` in `config.py`, default
`data/raw_gml/`) and a raw tree inventory parquet
(`RAW_TREES_SOURCE_PATH`, default `data/city_public.parquet`) — that are
not part of the checked-in `data/` listing above, since they are supplied
externally rather than tracked in this repository.
 
`example_shadow_ratio.py` is a usage example; its contents are not
reproduced in this document, but functionally it demonstrates the same
entry points listed in Section 2.4.2 below.

### 2.2 Requirements

- Python 3.12.10 (the version used for development and testing).
- See `requirements.txt` for package dependencies.

### 2.3 Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2.4 Usage

All commands below assume execution from the `shadow_map/` project root, so that relative data paths resolve correctly.

#### 2.4.1 One-time data preparation

The following steps convert raw source data into the form consumed by the rest of the codebase. They should be re-run only when the underlying data changes (e.g., new buildings or trees delivered, or a change of city or
year) rather than on every request.

```bash
# a. Preprocess raw sources into data/
python preprocess_buildings.py   # data/raw_gml/ -> data/buildings_geometry.fgb
python preprocess_trees.py       # data/city_public.parquet -> data/trees_geometry.fgb
 
# b. (Optional) Build the archival combined dataset. This is not used by
#    the live request path; it is a convenience artifact for offline
#    analysis.
python merge_buildings_and_trees.py   # -> data/merged_buildings_and_trees.fgb
 
# c. Precompute the sun-position grid for the reference year (see Section
#    2.6.1 for the rationale).
python -c "from calculate_sun_position import build_sun_position_grid; build_sun_position_grid()"
# -> data/grid_sun_pos.pkl
# For Magdeburg, 2026, this reduces 525,600 sampled minutes to 9,553
# distinct (azimuth, altitude) grid cells, which is the number of shadow
# maps step (d) computes.
 
# d. Precompute building shadow maps for every (azimuth, altitude) pair in
#    the grid produced above.
python precompute_shadows.py
# -> precomputed_shadows/shadow_az_{az}_alt_{alt}.parquet, one file per
#    grid cell.
```

#### 2.4.2 Runtime usage — entry points

Once `data/` and `precomputed_shadows/` are populated, the following are
the primary entry points for day-to-day use.

**Retrieving shadow coverage for an area at a given sun position:**

```python
from shadow_class import ShadowMap
from calculate_sun_position import get_sun_position, round_sun_position
from datetime import datetime, timezone
 
shadow_map = ShadowMap()
 
dt = datetime(2026, 6, 21, 15, 0, tzinfo=timezone.utc)
lon, lat = 11.6456, 52.1390
altitude, azimuth = get_sun_position(dt, lon, lat)
alt_key, az_key = round_sun_position(altitude, azimuth)
 
# bbox = (minx, miny, maxx, maxy), in longitude/latitude degrees
bbox = (11.640, 52.135, 11.650, 52.145)
 
union = shadow_map.get_shadow_union_metric(az_key, alt_key, bbox, buildings_only=True)
# Returns a single shapely geometry (in EPSG:25832) representing all shadow
# coverage within the given bbox at the given sun position, or None if
# there is no coverage. Set buildings_only=False to include tree shadows.
```

**Computing the shadow ratio of a specific line (e.g., one street edge):**

```python
ratio = shadow_map.shadow_ratio(edge_geom_metric, union)
# Returns a float in [0, 1]: the fraction of edge_geom_metric's length that
# is shaded. edge_geom_metric must be in the same metric CRS as `union`
# (EPSG:25832); see geo_utils.reproject_geoms / reproject_gdf.
```

**Computing the shadow ratio of an entire walking or driving route:**

```python
from compute_shadow_ratio import compute_static_shadow, compute_dynamic_shadow
 
start = {"lat": 52.1390, "lon": 11.6456}
end = {"lat": 52.1410, "lon": 11.6480}
query_dt = datetime(2026, 6, 21, 15, 0, tzinfo=timezone.utc)
 
# A single sun position for the entire route. Appropriate for short trips.
result = compute_static_shadow(start, end, query_dt, network_type="walk")
 
# Sun position re-evaluated per edge, at that edge's own estimated arrival
# time. More accurate for longer trips; the shadow is only recomputed when
# the sun's (azimuth, altitude) grid cell changes between edges.
result = compute_dynamic_shadow(start, end, query_dt, network_type="walk")
 
# Both functions return the same structure:
# {
#     "total_length_m": float,
#     "overall_shadow_ratio": float,   # length-weighted average, in [0, 1]
#     "edges": [
#         {
#             "length_m": float,
#             "shadow_ratio": float,
#             "altitude_deg": float,
#             "azimuth_deg": float,
#             "eval_datetime": str,
#         },
#         ...
#     ],
# }
```

**Visualizing precomputed shadows over the course of a day** (for
demonstration and quality assurance; not part of the request-serving path):
see `create_shadow_slide_visualization.py`, which reads directly from
`data/precomputed_shadows/` and renders an animated GIF.

#### 2.4.3 Tests
 
```bash
pytest test_shadow_model.py -v
```

Tests that require real data (most of those covering `shadow_class`,
`shadow_geometry`, and `compute_shadow_ratio`) read directly from the paths
defined in `config.py`. They are skipped, rather than failed, when the
corresponding data is not present.

### 2.5 Data

#### 2.5.1 Sources

- **Buildings**: [Sachsen-Anhalt Geodatenportal](https://www.lvermgeo.sachsen-anhalt.de/de/gdp-geodaten-karten.html)
  (CityGML building models).
- **Trees**: the same portal, combining public and private tree
  inventories.

#### 2.5.2 Before preprocessing (`data/raw/`)

| File | Columns | CRS |
|---|---|---|
| `buildings_geometry_original.fgb` | `building_id`, `part_id`, `height`, `geometry` | EPSG:25832 |
| `trees_geometry_original.fgb` | `Gattung lang`, `Stammumfang`, `Baumhoehe`, `Kronendurchmesser`, `Pflanzjahr`, `Objektbezeichnung`, `Objektart lang`, `baumnummer`, `geometry`, `source` | EPSG:25832 |

The raw tree columns are delivered in German: species (`Gattung lang`),
trunk circumference (`Stammumfang`), tree height (`Baumhoehe`), crown
diameter (`Kronendurchmesser`), planting year (`Pflanzjahr`), and object
description/type (`Objektbezeichnung`, `Objektart lang`). `preprocess_trees.py`
retains only `baumnummer`, `Baumhoehe`, `Kronendurchmesser`, and `geometry`;
the remaining fields are dropped when producing `trees_geometry.fgb`, as
they are not currently used downstream. If this metadata is required in the
future (for example, species-specific canopy density), `preprocess_trees.py`
must be modified to carry it through explicitly.

#### 2.5.3 After preprocessing (`data/processed/`)

| File | Columns | CRS |
|---|---|---|---|
| `buildings_geometry.fgb` | `building_id`, `height`, `geometry` | EPSG:4326 |
| `trees_geometry.fgb` | `tree_id`, `height`, `geometry` | EPSG:4326 |
| `merged_buildings_and_trees.fgb` | `id`, `height`, `geometry` | EPSG:4326 |

The `part_id` column in `buildings_geometry_original.fgb` (distinguishing
multiple polygon parts belonging to one building, e.g., where roof height
differs across sections) is consumed by the height-based
grouping/dissolving step in `preprocess_buildings.py`.

`merged_buildings_and_trees.fgb` is a static combination
of the two processed datasets, produced by `merge_buildings_and_trees.py`.


### 2.6 Design

#### 2.6.1 Precomputation strategy

Shadow geometry depends only on the sun's position (azimuth and altitude),
not on the calendar date directly. Computing a full shadow polygon set for
a city area is computationally expensive; however, when snapped to a 1°×1°
grid, the sun occupies a limited number of distinct positions over the
course of a year, and the same (azimuth, altitude) pair recurs on multiple
dates (the sun revisits similar positions at different times of year, for
example symmetrically around the solstices). Consequently, shadows are
precomputed per sun position rather than per date or time:

1. Sample the sun's position at one-minute resolution over a full year at
   the reference location (`build_sun_position_grid`).
2. Discard positions with altitude below `ALT_MIN` (2°), since shadow
   projections for the sun this low on the horizon are unbounded and
   unreliable.
3. Snap each remaining sample to a 1°×1° (azimuth, altitude) grid cell and
   retain only the set of distinct cells that occur.
4. Precompute and store one shadow map per distinct cell
   (`precompute_shadows.py`), for a fixed area of interest (currently the
   Magdeburg area, buildings only).

At request time, only the current (azimuth, altitude) is required; it is
snapped to the grid and used to look up (or, if outside the precomputed
area, compute) the corresponding shadow map. No per-request date awareness
is necessary.


#### 2.6.2 Asymmetric treatment of buildings and trees

Buildings are precomputed, since precomputation cost is substantial for a
large feature set covering a wide area and the geometry is static. Trees
are not precomputed.

Both source datasets are stored as FlatGeobuf (`.fgb`) rather than Parquet,
because FlatGeobuf supports genuine bounding-box-limited reads via GDAL
(`gpd.read_file(path, bbox=...)` reads only the relevant spatial extent).
GeoParquet bounding-box pushdown is not reliably available across the
project's geopandas version, so a Parquet source would require
loading the entire file per request. Precomputed shadow outputs, by
contrast, are small per-(azimuth, altitude) files and are stored as
Parquet for compact, columnar storage and fast full-file reads.


---

## 3. Thermal Comfort (`thermal_comfort/`)

### 3.1 Project layout

```
thermal_comfort/
    ├── thermal_comfort.py
    └── get_thermal_comfort.py
```

### 3.2 Description

This module estimates the Universal Thermal Climate Index (UTCI, Bröde
et al., 2012) from available environmental sensor or
forecast inputs: air temperature, relative humidity, wind speed, and,
optionally, wet-bulb globe temperature or globe temperature. Wind speed is
adjusted to the 10 m reference height using a logarithmic wind profile
prior to UTCI computation.

This module is currently independent of the Shadow Model. 

### 3.3 Installation

```bash
pip install -r thermal_comfort/requirements.txt
```

### 3.4 Usage

```python
from get_thermal_comfort import get_thermal_comfort

result = get_thermal_comfort(
    ta=28.0,    # air temperature, degrees Celsius
    rh=55.0,    # relative humidity, percent
    ws=3.0,     # wind speed, m/s
    wbgt=None,  # wet-bulb globe or globe temperature, °C; None estimates it from ta/rh
    height=3.5, # measurement height of the inputs, m
)
# Returns {"utci": <float, °C>, "stress_category": <str>}
```

The underlying `ThermalComfort` class, in `thermal_comfort.py`, provides
direct access to intermediate values (mean radiant temperature, globe
temperature, etc.) for cases requiring more than the simplified dictionary
returned by `get_thermal_comfort()`.

---

## 4. References

- Bröde, P., et al. (2012). Deriving the operational procedure for the
  Universal Thermal Climate Index (UTCI). *International Journal of
  Biometeorology*, 56(3), 481–494.
- Sachsen-Anhalt Geodatenportal (LVermGeo).
  https://www.lvermgeo.sachsen-anhalt.de/de/gdp-geodaten-karten.html
- Boeing, G. OSMnx: New methods for acquiring, constructing, analyzing, and
  visualizing complex street networks.

## 5. Acknowledgments

This work is part of the [IMIQ project](https://github.com/imiq-project/).

## 6. Contact
Questions, feedback, and collaboration inquiries are welcome by [email](iana.costa@ovgu.de)
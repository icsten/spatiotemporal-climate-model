import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
 
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation
from suncalc import get_position
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LAT           = 52.13896498167249
LON           = 11.645601397328756
SHADOW_DIR    = Path("./precomputed_shadows")
ALT_MIN       = 2

def deg(radians: float) -> float:
    return math.degrees(radians)

def compute_day_positions(start, end, step_minutes):
    step = timedelta(minutes=step_minutes)

    positions = []
    current = start

    while current < end:
        current_utc = current.astimezone(timezone.utc)
        sun_pos = get_position(current_utc, LON, LAT)
        alt = deg(float(sun_pos["altitude"]))
        az = (deg(float(sun_pos["azimuth"])) + 180) % 360

        az_key = round(az)
        alt_key = round(alt)
        print(f"Alt key: {alt_key} | Current time: {current}")

        if alt >= ALT_MIN:
            file_path = SHADOW_DIR / f"shadow_az_{az_key}_alt_{alt_key}.parquet"
            
            if not file_path.exists():
                print(f"  [MISSING] {current.strftime('%H:%M')} → az={az_key} alt={alt_key}")
            else:
                positions.append({
                    "time"   : current.strftime("%Y-%m-%d %H:%M"),
                    "az_raw" : round(az,  2),
                    "alt_raw": round(alt, 2),
                    "az_key" : az_key,
                    "alt_key": alt_key,
                    "parquet": file_path,
                })
        
        current += step
    return positions


def create_shadow_slide(buildings, positions, file_path, interval_ms=0, figsize=(12,10)):
    print("Pre loading shadow maps")
    cache: dict[str, gpd.GeoDataFrame | None] = {}
    missing = []

    for p in positions:
        key = p["time"]
        if p["parquet"].exists():
            cache[key] = gpd.read_parquet(p["parquet"])
        else:
            missing.append(key)
            cache[key] = None
    
    loaded = sum(1 for v in cache.values() if v is not None)
    print(f"Loaded: {loaded} shadow maps")
    if missing:
        print(f"Missing: {len(missing)}")

    bounds = buildings.total_bounds
    pad = (bounds[2] - bounds[0])*0.1   # %10 padding
    xlim      = (bounds[0] - pad, bounds[2] + pad)
    ylim      = (bounds[1] - pad, bounds[3] + pad)

    fig = plt.figure(figsize=figsize, facecolor="#FFFFFF")
    ax = fig.add_axes([0.0, 0.06, 1.0, 0.93])
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.set_aspect("auto")
    ax.set_facecolor("#E8E4DC")
    ax.axis("off")

    buildings.plot(ax=ax, color="#4A90D9", edgecolor="#2C5F8A", linewidth=0.5, zorder=2)

    shadow_collection = [None]

    # Info text
    fig.text(
        0.5, 0.975, "Shadow Simulation - Magdeburg, June 30 2026", ha="center", va="top", fontsize=14, color="#222222",
    )
    sun_text = ax.text(
        0.01, 0.99, "", transform=ax.transAxes,
        fontsize=11, va="top", ha="left", color="#333333",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", alpha=0.85),zorder=10,
    )

    time_text = fig.text(
        0.5, 0.055 if not file_path else 0.03,
        "",
        ha="center", va="center",
        fontsize=15, color="#222222",
    )

    # Legend
    legend_handles = [
        mpatches.Patch(facecolor="#4A90D9", edgecolor="#2C5F8A", label="Buildings"),
        mpatches.Patch(facecolor="#4A4A4A", alpha=0.45,           label="Shadows"),
    ]

    ax.legend(
            handles=legend_handles,
            loc="lower right",
            fontsize=10,
            framealpha=0.85,
        )

    def draw_frame(frame_idx: int) -> None:
        frame_idx = int(frame_idx)
        p   = positions[frame_idx]
        key = p["time"]
        gdf = cache.get(key)
 
        # Remove previous shadow layer
        if shadow_collection[0] is not None:
            shadow_collection[0].remove()
            shadow_collection[0] = None
 
        if gdf is not None and not gdf.empty:
            gdf.plot(ax=ax, color="#4A4A4A", alpha=0.45, zorder=1)
            shadow_collection[0] = ax.collections[-1]
 
        time_text.set_text(f"Time: {p['time']}")
        sun_text.set_text(f"az = {p['az_key']}° | alt = {p['alt_key']}°")
 
        fig.canvas.draw_idle()

   
    def update(frame_idx):
        draw_frame(frame_idx)
        return []

    anim = FuncAnimation(
        fig,
        update,
        frames=len(positions),
        interval=interval_ms,
        blit=False,
        repeat=True,
    )

    print(f"Saving animation to {file_path}")
    if file_path.endswith(".gif"):
        anim.save(file_path, writer="pillow", fps=1000 // interval_ms)
    else:
        anim.save(file_path, writer="ffmpeg", fps=1000 // interval_ms)
    print("Saved animation")

 
import networkx as nx
import osmnx as ox

WALK_SPEED_KPH_DEFAULT = 5.0
PAD_DEG_DEFAULT = 0.005

def get_route_edges(start_lat, start_lon, end_lat, end_lon, network_type="walk", walk_speed_kph=WALK_SPEED_KPH_DEFAULT, pad_deg=PAD_DEG_DEFAULT):
    bbox = (
        min(start_lon, end_lon) - pad_deg,
        min(start_lat, end_lat) - pad_deg,
        max(start_lon, end_lon) + pad_deg,
        max(start_lat, end_lat) + pad_deg,
    )
    G = ox.graph_from_bbox(bbox=bbox, network_type=network_type)
    
    if network_type=="drive":
        G = ox.routing.add_edge_speeds(G)
        G = ox.routing.add_edge_travel_times(G)
    else:
        for _, _, data in G.edges(data=True):
            data["speed_kph"] = walk_speed_kph
            data["travel_time"] = data["length"] / (walk_speed_kph * 1000 / 3600)

    start_node = ox.distance.nearest_nodes(G, start_lon, start_lat)
    end_node = ox.distance.nearest_nodes(G, end_lon, end_lat)

    route = nx.shortest_path(G, start_node, end_node, weight="length")
    if not route or len(route) < 2:
        return None, []
 
    edges_gdf = ox.routing.route_to_gdf(G, route).reset_index()
 
    edges = [
        {
            "u": row.u,
            "v": row.v,
            "geometry": row.geometry,
            "length_m": row.length,
            "travel_time_s": row.travel_time,
        }
        for row in edges_gdf.itertuples()
    ]
    return route, edges
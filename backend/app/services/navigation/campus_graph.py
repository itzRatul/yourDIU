"""
DIU Campus Navigation Graph
============================
Map data for Daffodil International University campus.
Nodes = named campus locations.
Edges = walkable paths with estimated distances (meters) and compass directions.

Dijkstra's algorithm finds the shortest route between any two locations.
"""

import heapq
import math

# ── Campus Locations ──────────────────────────────────────────────────────────

NODES = [
    "Admission Office",
    "Bike Garage",
    "Boat Lake",
    "Bonomaya",
    "Bonomaya 2",
    "Central Jame Mosque",
    "Department of Civil Engineering",
    "Department of EEE",
    "DIU Garden",
    "DIU Health and Fitness Center",
    "DIU Sports Dorm",
    "DIU Transport Hub",
    "DIU Zoo",
    "Food Court",
    "Golf Yard",
    "Green Garden",
    "Inspiration Building",
    "Knowledge Tower",
    "LAB Academic Building",
    "Main Gate 1",
    "Main Gate 2",
    "Main Gate 3",
    "Main Gate 4",
    "Main Gate 5",
    "Main Gate 6",
    "Main Gate 7",
    "Main Gate 8",
    "Main Gate 9",
    "Nursery",
    "RASG 1",
    "RASG 2",
    "Shadhinota Shommelon Kendro",
    "Shaheed Minar",
    "Kathal Tola",
    "Volleyball Court",
    "YKSG 1",
    "YKSG 2",
    "DIU Logo",
]

# ── Edges: (from, to, distance_meters, direction_forward, direction_backward) ─

EDGES = [
    ("Admission Office",              "Shaheed Minar",               20, "West",       "East"),
    ("Admission Office",              "Volleyball Court",             15, "East",       "West"),
    ("Volleyball Court",              "Green Garden",                 15, "East",       "West"),
    ("Knowledge Tower",               "Kathal Tola",                  25, "South",      "North"),
    ("Knowledge Tower",               "Bike Garage",                  30, "North",      "South"),
    ("Bike Garage",                   "Shadhinota Shommelon Kendro",  30, "North-East", "South-West"),
    ("Bike Garage",                   "RASG 2",                       35, "North",      "South"),
    ("RASG 2",                        "Shadhinota Shommelon Kendro",  20, "East",       "West"),
    ("Green Garden",                  "LAB Academic Building",        20, "North-East", "South-West"),
    ("LAB Academic Building",         "Central Jame Mosque",          15, "North-West", "South-East"),
    ("Central Jame Mosque",           "Inspiration Building",         20, "North",      "South"),
    ("Inspiration Building",          "DIU Transport Hub",            25, "East",       "West"),
    ("Inspiration Building",          "Nursery",                      25, "North-West", "South-East"),
    ("Inspiration Building",          "Bonomaya",                     25, "North",      "South"),
    ("Nursery",                       "Food Court",                   20, "North",      "South"),
    ("Food Court",                    "Bonomaya",                     15, "East",       "West"),
    ("Bonomaya",                      "DIU Garden",                   20, "North",      "South"),
    ("DIU Health and Fitness Center", "Food Court",                   15, "South",      "North"),
    ("DIU Sports Dorm",               "Shadhinota Shommelon Kendro",  15, "South",      "North"),
    ("DIU Zoo",                       "RASG 1",                       20, "East",       "West"),
    ("DIU Health and Fitness Center", "Boat Lake",                    25, "North",      "South"),
    ("DIU Health and Fitness Center", "RASG 1",                       30, "East",       "West"),
    ("DIU Garden",                    "DIU Health and Fitness Center", 20, "West",      "East"),
    ("RASG 1",                        "Bonomaya 2",                   25, "South-East", "North-West"),
    ("DIU Zoo",                       "Bonomaya 2",                   20, "South",      "North"),
    ("Boat Lake",                     "Main Gate 7",                  30, "North",      "South"),
    ("Main Gate 7",                   "Department of EEE",            40, "North-West", "South-East"),
    ("Department of EEE",             "Department of Civil Engineering", 35, "North",   "South"),
    ("Golf Yard",                     "Shaheed Minar",                25, "East",       "West"),
    ("Golf Yard",                     "Kathal Tola",                  20, "North",      "South"),
    ("Main Gate 1",                   "Admission Office",             15, "North",      "South"),
    ("Main Gate 2",                   "Admission Office",             15, "North",      "South"),
    ("Main Gate 3",                   "Green Garden",                 15, "North",      "South"),
    ("Main Gate 4",                   "Knowledge Tower",              15, "East",       "West"),
    ("Main Gate 5",                   "Bike Garage",                  15, "East",       "West"),
    ("Main Gate 6",                   "Shadhinota Shommelon Kendro",  20, "South",      "North"),
    ("Main Gate 7",                   "YKSG 2",                       25, "East",       "West"),
    ("Main Gate 8",                   "Main Gate 9",                  25, "North-East", "South-West"),
    ("Main Gate 8",                   "YKSG 1",                       30, "South",      "North"),
    ("Bonomaya 2",                    "Main Gate 9",                  25, "South",      "North"),
    ("DIU Transport Hub",             "Main Gate 8",                  35, "East",       "West"),
    ("Main Gate 6",                   "Boat Lake",                    15, "North-East", "South-West"),
    ("DIU Logo",                      "Knowledge Tower",              25, "West",       "East"),
    ("DIU Logo",                      "Shadhinota Shommelon Kendro",  35, "North",      "South"),
    ("DIU Logo",                      "Inspiration Building",         45, "East",       "West"),
]


# ── Graph builder ─────────────────────────────────────────────────────────────

def _build_graph() -> dict:
    graph = {node: {} for node in NODES}
    for u, v, w, dir_uv, dir_vu in EDGES:
        graph[u][v] = {"weight": w, "direction": dir_uv}
        graph[v][u] = {"weight": w, "direction": dir_vu}
    return graph


GRAPH = _build_graph()


# ── Dijkstra ──────────────────────────────────────────────────────────────────

def dijkstra(start: str) -> tuple[dict, dict]:
    distances = {node: math.inf for node in GRAPH}
    previous  = {node: None     for node in GRAPH}
    distances[start] = 0
    heap = [(0, start)]

    while heap:
        cur_dist, cur_node = heapq.heappop(heap)
        if cur_dist > distances[cur_node]:
            continue
        for neighbor, edge in GRAPH[cur_node].items():
            tentative = cur_dist + edge["weight"]
            if tentative < distances[neighbor]:
                distances[neighbor] = tentative
                previous[neighbor]  = cur_node
                heapq.heappush(heap, (tentative, neighbor))

    return distances, previous


def reconstruct_path(previous: dict, start: str, end: str) -> list[str]:
    path, cur = [], end
    while cur is not None:
        path.append(cur)
        cur = previous.get(cur)
    path.reverse()
    return path if (path and path[0] == start) else []


def get_directions(path: list[str]) -> list[str]:
    """Turn-by-turn compass directions for each step in the path."""
    if len(path) <= 1:
        return ["You are already at your destination!"]
    return [
        f"Walk {GRAPH[path[i]][path[i+1]]['direction']} towards {path[i+1]}."
        for i in range(len(path) - 1)
    ]

"""
Campus Navigator
================
Detects navigation queries in chat messages and computes the shortest route
using Dijkstra's algorithm on the DIU campus graph.

Intent detection:
  - Looks for navigation keywords (English + Bangla + Banglish)
  - Fuzzy-matches location names from the user's message
  - Returns a structured route context string for the LLM to present naturally

This module has no LLM calls — it is pure algorithm + string formatting.
The formatted route is injected into the LLM prompt by brain_service.
"""

import math
import re
from difflib import SequenceMatcher

from .campus_graph import NODES, GRAPH, dijkstra, reconstruct_path, get_directions

# ── Navigation intent keywords ────────────────────────────────────────────────

_NAV_KEYWORDS = [
    # English
    "navigate", "navigation", "route", "path", "direction", "directions",
    "how to go", "how to get", "how do i go", "how do i get",
    "way to", "way from", "get to", "get from",
    "shortcut",
    # Banglish
    "jabo", "jaite", "jete chai", "jate chai", "jaibo", "jawa",
    "kivabe jabo", "kivabe jaibo", "kivabe jete",
    "kothay jabo", "kothay jaite", "kothay jete",
    "rasta", "rastay", "path dekao", "path dao",
    # Bangla
    "যাবো", "যাব", "যেতে", "যেতে চাই", "যাই কিভাবে",
    "রাস্তা", "পথ", "দিক", "দিকনির্দেশনা",
    "কিভাবে যাবো", "কিভাবে যাব", "কিভাবে যেতে",
    "কোথায় যাবো", "কোথায় যাব",
]

# Common aliases / alternate spellings for locations
_ALIASES: dict[str, str] = {
    # Gates
    "gate 1": "Main Gate 1",
    "gate 2": "Main Gate 2",
    "gate 3": "Main Gate 3",
    "gate 4": "Main Gate 4",
    "gate 5": "Main Gate 5",
    "gate 6": "Main Gate 6",
    "gate 7": "Main Gate 7",
    "gate 8": "Main Gate 8",
    "gate 9": "Main Gate 9",
    "main gate1": "Main Gate 1",
    "main gate2": "Main Gate 2",
    "main gate3": "Main Gate 3",
    "main gate4": "Main Gate 4",
    "main gate5": "Main Gate 5",
    "main gate6": "Main Gate 6",
    "main gate7": "Main Gate 7",
    "main gate8": "Main Gate 8",
    "main gate9": "Main Gate 9",
    # Buildings
    "mosque": "Central Jame Mosque",
    "masjid": "Central Jame Mosque",
    "jame mosque": "Central Jame Mosque",
    "eee": "Department of EEE",
    "civil": "Department of Civil Engineering",
    "civil dept": "Department of Civil Engineering",
    "eee dept": "Department of EEE",
    "lab": "LAB Academic Building",
    "lab building": "LAB Academic Building",
    "food": "Food Court",
    "foodcourt": "Food Court",
    "cafeteria": "Food Court",
    "canteen": "Food Court",
    "transport": "DIU Transport Hub",
    "transport hub": "DIU Transport Hub",
    "bus stand": "DIU Transport Hub",
    "garden": "DIU Garden",
    "diu garden": "DIU Garden",
    "zoo": "DIU Zoo",
    "diu zoo": "DIU Zoo",
    "gym": "DIU Health and Fitness Center",
    "fitness": "DIU Health and Fitness Center",
    "health center": "DIU Health and Fitness Center",
    "sports dorm": "DIU Sports Dorm",
    "dorm": "DIU Sports Dorm",
    "bike": "Bike Garage",
    "bike garage": "Bike Garage",
    "garage": "Bike Garage",
    "knowledge": "Knowledge Tower",
    "kt": "Knowledge Tower",
    "inspiration": "Inspiration Building",
    "volleyball": "Volleyball Court",
    "v court": "Volleyball Court",
    "shaheed": "Shaheed Minar",
    "minar": "Shaheed Minar",
    "boat": "Boat Lake",
    "lake": "Boat Lake",
    "nursery": "Nursery",
    "golf": "Golf Yard",
    "logo": "DIU Logo",
    "diu logo": "DIU Logo",
    "admission": "Admission Office",
    "rasg1": "RASG 1",
    "rasg2": "RASG 2",
    "yksg1": "YKSG 1",
    "yksg2": "YKSG 2",
    "shommelon": "Shadhinota Shommelon Kendro",
    "shadhinota": "Shadhinota Shommelon Kendro",
    "kathal": "Kathal Tola",
    "bonomaya": "Bonomaya",
    "green": "Green Garden",
}

# Normalised node names for matching
_NODE_LOWER = {n.lower(): n for n in NODES}


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _fuzzy_score(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def find_location(text: str) -> str | None:
    """
    Return the canonical node name that best matches `text`, or None.
    Tries exact → alias → substring → fuzzy.
    """
    t = _normalise(text)

    # Exact
    if t in _NODE_LOWER:
        return _NODE_LOWER[t]

    # Alias
    if t in _ALIASES:
        return _ALIASES[t]

    # Substring of a node name or vice-versa
    for node_lower, node in _NODE_LOWER.items():
        if t in node_lower or node_lower in t:
            return node

    # Fuzzy (threshold 0.65)
    best_score, best_node = 0.0, None
    for node_lower, node in _NODE_LOWER.items():
        score = _fuzzy_score(t, node_lower)
        if score > best_score:
            best_score, best_node = score, node
    if best_score >= 0.65:
        return best_node

    return None


def _find_all_locations_in_query(query: str) -> list[tuple[int, str]]:
    """
    Return [(position, canonical_node), ...] sorted by position in the query.
    We try every NODES name and every alias as a sliding window.
    """
    q_lower = query.lower()
    found: dict[str, int] = {}  # node → earliest position

    # Try each node name
    for node in NODES:
        nl = node.lower()
        pos = q_lower.find(nl)
        if pos != -1:
            if node not in found or pos < found[node]:
                found[node] = pos

    # Try aliases
    for alias, node in _ALIASES.items():
        pos = q_lower.find(alias)
        if pos != -1:
            if node not in found or pos < found[node]:
                found[node] = pos

    # Sort by position
    return sorted(found.items(), key=lambda x: x[1])  # (node, pos) → sort by pos


def is_navigation_query(query: str) -> bool:
    """True if the query looks like a navigation request."""
    q = query.lower()
    return any(kw in q for kw in _NAV_KEYWORDS)


def detect_navigation_intent(query: str) -> tuple[str, str] | None:
    """
    Return (start_node, end_node) if the query is a navigation request
    with two identifiable campus locations. Returns None otherwise.

    The first location in the text is treated as the starting point,
    the last as the destination.
    """
    if not is_navigation_query(query):
        return None

    located = _find_all_locations_in_query(query)

    if len(located) < 2:
        return None

    start = located[0][0]
    end   = located[-1][0]

    if start == end:
        return None

    return start, end


def get_route_context(start: str, end: str) -> str:
    """
    Run Dijkstra and return a formatted route description suitable for
    injecting into an LLM system prompt as factual context.

    The LLM should then present this naturally in the user's language.
    """
    if start not in GRAPH or end not in GRAPH:
        return f"Navigation error: unknown location(s) '{start}' or '{end}'."

    distances, previous = dijkstra(start)
    path = reconstruct_path(previous, start, end)

    if not path:
        return (
            f"No walkable route found between '{start}' and '{end}' "
            "in the current campus map."
        )

    total_meters = distances[end]
    directions   = get_directions(path)

    steps_text = "\n".join(
        f"  Step {i+1}: {step}" for i, step in enumerate(directions)
    )

    return (
        f"CAMPUS NAVIGATION RESULT (Dijkstra's shortest path):\n"
        f"  From : {start}\n"
        f"  To   : {end}\n"
        f"  Total distance: {total_meters} meters\n"
        f"  Number of stops: {len(path) - 1}\n"
        f"  Full route: {' → '.join(path)}\n\n"
        f"Turn-by-turn directions:\n{steps_text}\n"
        f"  Final step: You have arrived at {end}!\n\n"
        f"Present this route clearly and helpfully to the user. "
        f"List each step on a new line. Use the same language as the user (Bangla or English)."
    )


def list_all_locations() -> str:
    """Return a formatted list of all campus locations (for when user asks 'what places do you know?')."""
    return "Known campus locations:\n" + "\n".join(f"  • {n}" for n in sorted(NODES))

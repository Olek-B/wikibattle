"""Wikipedia API wrapper for WikiBattle.

Fetches random articles and extracts relevant metadata for card generation.
"""

import requests
import re
from typing import Optional

WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "WikiBattle/1.0 (card game; educational)"

# Category keywords used to classify articles into card types
PERSON_KEYWORDS = [
    "births", "deaths", "living people", "people from",
    "alumni", "politicians", "actors", "actresses", "singers",
    "writers", "athletes", "players", "musicians", "scientists",
    "presidents", "monarchs", "composers", "directors", "artists",
    "philosophers", "mathematicians", "engineers", "generals",
    "admirals", "officers", "coaches", "footballers", "swimmers",
    "runners", "boxers", "wrestlers",
]

ANIMAL_KEYWORDS = [
    "animals", "mammals", "birds", "reptiles", "fish", "insects",
    "amphibians", "arachnids", "molluscs", "crustaceans",
    "species described", "fauna of", "endangered species",
    "dog breeds", "cat breeds", "horse breeds",
    "dinosaurs", "prehistoric",
]

EVENT_KEYWORDS = [
    "battles", "wars", "conflicts", "treaties", "revolutions",
    "disasters", "earthquakes", "floods", "hurricanes", "volcanic eruptions",
    "epidemics", "pandemics", "famines",
    "elections", "referendums", "coups", "protests", "riots",
    "massacres", "assassinations", "bombings", "attacks",
    "expeditions", "voyages", "missions",
    "festivals", "ceremonies", "events in",
    "incidents", "accidents", "scandals",
    "acts of", "legislation",
]

PLACE_KEYWORDS = [
    "cities", "towns", "villages", "municipalities", "counties",
    "provinces", "states", "countries", "regions", "districts",
    "populated places", "geography of", "landforms",
    "mountains", "rivers", "lakes", "islands", "valleys",
    "deserts", "forests", "parks", "reserves",
    "buildings", "structures", "bridges", "castles", "churches",
    "cathedrals", "mosques", "temples", "palaces", "stadiums",
    "airports", "stations", "ports", "dams",
    "world heritage sites", "monuments", "landmarks",
    "coordinates on wikidata",
]


def _session() -> requests.Session:
    """Create a requests session with proper headers."""
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def fetch_random_articles(count: int = 20) -> list[dict]:
    """Fetch random Wikipedia articles with full metadata.

    Returns a list of article dicts with keys:
        pageid, title, extract, thumbnail, categories, coordinates, url
    """
    # We fetch more than needed because some articles may be stubs
    fetch_count = min(count * 3, 50)
    session = _session()

    params = {
        "action": "query",
        "format": "json",
        "generator": "random",
        "grnnamespace": 0,
        "grnlimit": fetch_count,
        "grnfilterredir": "nonredirects",
        "prop": "extracts|pageimages|categories|coordinates",
        "exintro": True,
        "explaintext": True,
        "exsectionformat": "plain",
        "pithumbsize": 300,
        "cllimit": 20,
        "colimit": 50,
    }

    try:
        resp = session.get(WIKI_API, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    pages = data.get("query", {}).get("pages", {})
    articles = []

    for page_id, page in pages.items():
        extract = page.get("extract", "")
        # Skip very short stubs
        if len(extract) < 80:
            continue

        categories = [
            c.get("title", "").replace("Category:", "").lower()
            for c in page.get("categories", [])
        ]

        coords = None
        if "coordinates" in page:
            c = page["coordinates"][0]
            coords = {"lat": c["lat"], "lon": c["lon"]}

        thumbnail = None
        if "thumbnail" in page:
            thumbnail = page["thumbnail"]["source"]

        articles.append({
            "pageid": page.get("pageid"),
            "title": page.get("title", "Unknown"),
            "extract": extract[:500],  # Trim for AI prompt size
            "thumbnail": thumbnail,
            "categories": categories,
            "coordinates": coords,
            "url": f"https://en.wikipedia.org/wiki/{page.get('title', '').replace(' ', '_')}",
        })

    return articles[:count]


def fetch_articles_with_coordinates(count: int = 10) -> list[dict]:
    """Fetch random geographic articles (articles with coordinates).

    Uses geosearch with random coordinates to find place articles.
    """
    import random
    session = _session()
    articles = []

    # Generate random geographic points and search near them
    attempts = 0
    while len(articles) < count and attempts < count * 2:
        attempts += 1
        lat = random.uniform(-60, 70)  # Avoid extreme poles
        lon = random.uniform(-180, 180)

        params = {
            "action": "query",
            "format": "json",
            "list": "geosearch",
            "gscoord": f"{lat}|{lon}",
            "gsradius": 10000,  # 10km radius
            "gslimit": 5,
        }

        try:
            resp = session.get(WIKI_API, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError):
            continue

        geo_results = data.get("query", {}).get("geosearch", [])
        if not geo_results:
            continue

        # Get full details for these pages
        page_ids = [str(r["pageid"]) for r in geo_results]
        detail_params = {
            "action": "query",
            "format": "json",
            "pageids": "|".join(page_ids),
            "prop": "extracts|pageimages|categories|coordinates",
            "exintro": True,
            "explaintext": True,
            "pithumbsize": 300,
            "cllimit": 20,
        }

        try:
            resp2 = session.get(WIKI_API, params=detail_params, timeout=10)
            resp2.raise_for_status()
            data2 = resp2.json()
        except (requests.RequestException, ValueError):
            continue

        for pid, page in data2.get("query", {}).get("pages", {}).items():
            extract = page.get("extract", "")
            if len(extract) < 50:
                continue

            categories = [
                c.get("title", "").replace("Category:", "").lower()
                for c in page.get("categories", [])
            ]

            coords = None
            if "coordinates" in page:
                c = page["coordinates"][0]
                coords = {"lat": c["lat"], "lon": c["lon"]}
            else:
                # Use the geosearch coords
                for gr in geo_results:
                    if str(gr["pageid"]) == pid:
                        coords = {"lat": gr["lat"], "lon": gr["lon"]}
                        break

            thumbnail = None
            if "thumbnail" in page:
                thumbnail = page["thumbnail"]["source"]

            articles.append({
                "pageid": page.get("pageid"),
                "title": page.get("title", "Unknown"),
                "extract": extract[:500],
                "thumbnail": thumbnail,
                "categories": categories,
                "coordinates": coords,
                "url": f"https://en.wikipedia.org/wiki/{page.get('title', '').replace(' ', '_')}",
            })

    return articles[:count]


def classify_article(article: dict) -> str:
    """Classify a Wikipedia article into a card type.

    Returns one of: 'creature', 'terrain', 'spell'

    Logic:
    - If it has coordinates -> terrain
    - If categories match person/animal keywords -> creature
    - If categories match event keywords -> spell
    - Fallback: use extract content heuristics
    """
    categories = article.get("categories", [])
    cat_text = " ".join(categories)
    extract = article.get("extract", "").lower()

    # Articles with coordinates are terrains
    if article.get("coordinates"):
        # Unless they're clearly a person (some people articles have coords)
        person_score = sum(1 for kw in PERSON_KEYWORDS if kw in cat_text)
        if person_score >= 2:
            return "creature"
        return "terrain"

    # Check for person/animal (creature)
    person_score = sum(1 for kw in PERSON_KEYWORDS if kw in cat_text)
    animal_score = sum(1 for kw in ANIMAL_KEYWORDS if kw in cat_text)

    # Check for event (spell)
    event_score = sum(1 for kw in EVENT_KEYWORDS if kw in cat_text)

    # Check for place (terrain)
    place_score = sum(1 for kw in PLACE_KEYWORDS if kw in cat_text)

    scores = {
        "creature": person_score + animal_score,
        "spell": event_score,
        "terrain": place_score,
    }

    best = max(scores, key=lambda k: scores[k])
    if scores[best] > 0:
        return best

    # Fallback heuristics from extract text
    # Birth/death years pattern -> person
    if re.search(r"\(\d{4}\s*[-–]\s*\d{4}\)", extract) or \
       re.search(r"\(born\s+\d", extract):
        return "creature"

    # "is a" pattern with animal words
    if re.search(r"is a (species|genus|family|breed|type of)", extract):
        return "creature"

    # Location patterns
    if re.search(r"is a (city|town|village|river|mountain|lake|island|country|region|municipality)", extract):
        return "terrain"

    # Event patterns
    if re.search(r"(took place|occurred|happened|was fought|broke out)", extract):
        return "spell"

    # Default: creature (most Wikipedia articles are about people)
    return "creature"

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
    # Nationality-based person categories (very common on Wikipedia)
    "american people", "british people", "french people", "german people",
    "italian people", "spanish people", "russian people", "chinese people",
    "japanese people", "indian people", "canadian people", "australian people",
    "brazilian people", "mexican people", "dutch people", "swedish people",
    "polish people", "irish people", "scottish people", "korean people",
    "norwegian people", "danish people", "finnish people",
    # Additional professions/roles
    "sportspeople", "managers", "novelists", "poets", "journalists",
    "lawyers", "professors", "nobel laureates", "recipients of",
    "commanders", "people of", "comedians", "broadcasters",
    "philanthropists", "explorers", "inventors", "entrepreneurs",
    "physicians", "surgeons", "architects", "designers",
    "olympic", "medalists", "champions", "competitors",
    "women", "men",  # gendered category markers
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
    # Additional place categories
    "census-designated places", "unincorporated communities",
    "neighbourhoods", "neighborhoods", "suburbs", "communes",
    "cantons", "territories", "capitals", "metropolitan areas",
    "bays", "capes", "peninsulas", "plateaus", "glaciers",
    "waterfalls", "caves", "reefs", "wetlands",
    "protected areas", "archaeological sites", "historical sites",
    "bodies of water", "tributaries", "headlands",
    "national parks", "nature reserves", "heritage sites",
    "located in", "geography", "places in",
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
    - If it has coordinates -> terrain (unless clearly a person)
    - Score categories against person/animal, event, and place keywords
    - Fallback: use extract content heuristics
    - Tiebreaker: creature > terrain > spell (most Wikipedia articles are about people)
    """
    categories = article.get("categories", [])
    cat_text = " ".join(categories)
    extract = article.get("extract", "").lower()

    # Articles with coordinates are terrains
    if article.get("coordinates"):
        # Unless they're clearly a person (some people articles have coords)
        person_score = sum(1 for kw in PERSON_KEYWORDS if kw in cat_text)
        if person_score >= 1:
            return "creature"
        return "terrain"

    # Check for person/animal (creature)
    person_score = sum(1 for kw in PERSON_KEYWORDS if kw in cat_text)
    animal_score = sum(1 for kw in ANIMAL_KEYWORDS if kw in cat_text)

    # Check for event (spell)
    event_score = sum(1 for kw in EVENT_KEYWORDS if kw in cat_text)

    # Check for place (terrain)
    place_score = sum(1 for kw in PLACE_KEYWORDS if kw in cat_text)

    creature_score = person_score + animal_score

    # If any category matched, use scoring with tiebreaker
    if creature_score > 0 or event_score > 0 or place_score > 0:
        # Tiebreaker: creature > terrain > spell
        # Use tuples so (score, priority) breaks ties deterministically
        scored = [
            (creature_score, 2, "creature"),
            (place_score,    1, "terrain"),
            (event_score,    0, "spell"),
        ]
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return scored[0][2]

    # Fallback heuristics from extract text
    # Birth/death years pattern -> person
    if re.search(r"\(\d{4}\s*[-–]\s*\d{4}\)", extract) or \
       re.search(r"\(born\s+\d", extract):
        return "creature"

    # "was a/an" or "is a/an" followed by a profession/role -> person
    if re.search(r"(is|was) an? .{0,30}\b(politician|singer|actor|actress|writer|"
                 r"player|musician|scientist|artist|poet|author|composer|director|"
                 r"professor|lawyer|journalist|engineer|physician|architect|"
                 r"footballer|athlete|soldier|general|admiral|monarch|emperor|"
                 r"empress|king|queen|prince|princess|saint|prophet|philosopher|"
                 r"explorer|inventor|entrepreneur|comedian|broadcaster)\b", extract):
        return "creature"

    # "is a" pattern with animal/biological words
    if re.search(r"is a (species|genus|family|breed|type of|subspecies|order of)", extract):
        return "creature"

    # Location patterns
    if re.search(r"is a (city|town|village|river|mountain|lake|island|country|"
                 r"region|municipality|commune|neighborhood|neighbourhood|suburb|"
                 r"census-designated place|unincorporated community|hamlet|"
                 r"borough|district|province|state|territory|peninsula|"
                 r"bay|cape|plateau|glacier|waterfall|cave|national park)", extract):
        return "terrain"

    # "located in" or "situated in" -> place
    if re.search(r"(is |are )?(located|situated) in", extract):
        return "terrain"

    # Event patterns
    if re.search(r"(took place|occurred|happened|was fought|broke out|was signed|was held)", extract):
        return "spell"

    # Default: creature (most Wikipedia articles are about people)
    return "creature"

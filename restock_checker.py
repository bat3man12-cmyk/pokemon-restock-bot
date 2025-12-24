import os
import requests
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# ================= CONFIG =================

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
USER_POSTCODE = "DN9"
MAX_DISTANCE_MILES = 30
SEEN_FILES = "seen_items.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (PokemonRestockChecker/1.0)"
}

if not DISCORD_WEBHOOK:
    raise RuntimeError("DISCORD_WEBHOOK environment variable missing")

# ================= LOCATION =================

geolocator = Nominatim(user_agent="pokemon_checker")
location = geolocator.geocode(USER_POSTCODE)

if not location:
    raise RuntimeError("Failed to geocode postcode")

USER_COORD = (location.latitude, location.longitude)

# ================= KEYWORDS =================

SEALED_KEYWORDS = [
    "booster",
    "elite trainer box",
    "etb",
    "tin",
    "collection",
    "blister",
    "trading card",
]

IGNORE_KEYWORDS = [
    "single",
    "guide",
    "book",
    "magazine",
    "proxy",
]

# ================= HELPERS =================

# ================= HELPERS =================

def is_sealed(name: str) -> bool:
    name = name.lower()
    return any(k in name for k in SEALED_KEYWORDS) and not any(
        i in name for i in IGNORE_KEYWORDS
    )

def within_distance(coord):
    return geodesic(USER_COORD, coord).miles <= MAX_DISTANCE_MILES

def send_discord(message: str):
    requests.post(DISCORD_WEBHOOK, json={"content": message}, timeout=10)

def get_soup(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    return BeautifulSoup(r.text, "html.parser")

def load_seen_items():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_seen_items(seen_items):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for item in sorted(seen_items):
            f.write(item + "\n")


# ============DEDUPLICATION ===============
    def load_seen_items():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_seen_items(seen_items):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for item in sorted(seen_items):
            f.write(item + "\n")


# ================= PER-STORE PARSERS =================

def parse_smyths(url):
    soup = get_soup(url)
    return [p.text.strip() for p in soup.select("h2.product-name") if is_sealed(p.text)]

def parse_entertainer(url):
    soup = get_soup(url)
    return [p.text.strip() for p in soup.select("a.product-name") if is_sealed(p.text)]

def parse_argos(url):
    soup = get_soup(url)
    return [
        p.text.strip()
        for p in soup.select("div[data-test='component-product-card-title']")
        if is_sealed(p.text)
    ]

def parse_whsmith(url):
    soup = get_soup(url)
    return [p.text.strip() for p in soup.select("h3") if is_sealed(p.text)]

def parse_forbidden_planet(url):
    soup = get_soup(url)
    return [p.text.strip() for p in soup.select("h3.product-title") if is_sealed(p.text)]

def parse_waterstones(url):
    soup = get_soup(url)
    return [p.text.strip() for p in soup.select("a.title") if is_sealed(p.text)]

def parse_cex(url):
    soup = get_soup(url)
    return [p.text.strip() for p in soup.select("h3") if is_sealed(p.text)]

def generic_parser(url):
    soup = get_soup(url)
    return [
        t.strip()
        for t in soup.stripped_strings
        if "pokemon" in t.lower()
        and 10 < len(t) < 120
        and is_sealed(t)
    ]

# ================= STORES =================

STORES = {
    "Smyths Toys": {
        "url": "https://www.smythstoys.com/uk/en-gb/search/?text=pokemon",
        "coord": (53.552, -1.128),
        "parser": parse_smyths,
    },
    "The Entertainer": {
        "url": "https://www.thetoyshop.com/search/?text=pokemon",
        "coord": (53.521, -1.120),
        "parser": parse_entertainer,
    },
    "Argos": {
        "url": "https://www.argos.co.uk/search/pokemon-trading-cards/",
        "coord": (53.525, -1.130),
        "parser": parse_argos,
    },
    "WHSmith": {
        "url": "https://www.whsmith.co.uk/search?query=pokemon",
        "coord": (53.518, -1.121),
        "parser": parse_whsmith,
    },
    "Forbidden Planet": {
        "url": "https://forbiddenplanet.com/catalogsearch/result/?q=pokemon",
        "coord": USER_COORD,
        "parser": parse_forbidden_planet,
    },
    "Waterstones": {
        "url": "https://www.waterstones.com/books/search/term/pokemon",
        "coord": USER_COORD,
        "parser": parse_waterstones,
    },
    "CEX": {
        "url": "https://uk.webuy.com/search/?query=pokemon",
        "coord": USER_COORD,
        "parser": parse_cex,
    },
    "Amazon UK": {
        "url": "https://www.amazon.co.uk/s?k=pokemon+tcg",
        "coord": USER_COORD,
        "parser": generic_parser,
    },
    "eBay UK": {
        "url": "https://www.ebay.co.uk/sch/i.html?_nkw=pokemon+tcg",
        "coord": USER_COORD,
        "parser": generic_parser,
    },
    "ASDA": {
        "url": "https://groceries.asda.com/search/pokemon",
        "coord": USER_COORD,
        "parser": generic_parser,
    },
    "Tesco": {
        "url": "https://www.tesco.com/groceries/en-GB/search?query=pokemon",
        "coord": USER_COORD,
        "parser": generic_parser,
    },
    "Morrisons": {
        "url": "https://groceries.morrisons.com/search?searchTerm=pokemon",
        "coord": USER_COORD,
        "parser": generic_parser,
    },
    "Sainsbury's": {
        "url": "https://www.sainsburys.co.uk/shop/gb/groceries/search?search-term=pokemon",
        "coord": USER_COORD,
        "parser": generic_parser,
    },
    "Aldi": {
        "url": "https://www.aldi.co.uk/search?query=pokemon",
        "coord": USER_COORD,
        "parser": generic_parser,
    },
    "B&M": {
        "url": "https://www.bmstores.co.uk/brands/pok-mon",
        "coord": USER_COORD,
        "parser": generic_parser,
    },
}

# ================= MAIN =================

def run():
    seen_items = load_seen_items()
    updated_seen = set(seen_items)
    
    for store, cfg in STORES.items():

        if cfg["coord"] != USER_COORD and not within_distance(cfg["coord"]):
            continue

        try:
            items = cfg["parser"](cfg["url"])
            if not items:
                continue

            new_items = [item for item in items if item not in seen_items]
            if not new_items:
                continue
                
            message = f"STORE RESTOCK DETECTED: {store} ({USER_POSTCODE})\n\n"
            for item in new_items[:10]:
                message += f"- {item}\n"
                updated_seen.add(item)

            send_discord(message)

        except Exception as e:
            print(f"{store} error: {e}")

save_unseen_items(updated_seen)

if __name__ == "__main__":
    send_discord("TEST MESSAGE: GitHub Actions can send Discord messages")
    run()





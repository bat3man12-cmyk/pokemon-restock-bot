import os
import time
import requests
from bs4 import BeautifulSoup
from geopy.distance import geodesic
from concurrent.futures import ThreadPoolExecutor

# ================= CONFIG =================

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
if not DISCORD_WEBHOOK:
    raise RuntimeError("DISCORD_WEBHOOK environment variable missing")

USER_COORD = (53.494, -0.934)  # DN9
USER_LOCATION_LABEL = "DN9"

DEFAULT_RADIUS_MILES = 30
SEEN_FILE = "seen_items.txt"
DISCORD_COOLDOWN_SECONDS = 1800  # 30 mins
LAST_SENT_FILE = "last_sent.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (PokemonRestockChecker/1.0)"
}

# ================= KEYWORDS =================

SEALED_KEYWORDS = [
    "booster", "elite trainer box", "etb",
    "tin", "collection", "blister", "trading card"
]

IGNORE_KEYWORDS = [
    "single", "guide", "book", "magazine", "proxy"
]

# ================= HELPERS =================

def is_sealed(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in SEALED_KEYWORDS) and not any(i in n for i in IGNORE_KEYWORDS)

def within_distance(store_coord, radius):
    return geodesic(USER_COORD, store_coord).miles <= radius

def can_send_discord():
    if not os.path.exists(LAST_SENT_FILE):
        return True
    with open(LAST_SENT_FILE, "r") as f:
        last = float(f.read().strip())
    return (time.time() - last) >= DISCORD_COOLDOWN_SECONDS

def mark_discord_sent():
    with open(LAST_SENT_FILE, "w") as f:
        f.write(str(time.time()))

def send_discord(message: str):
    if not can_send_discord():
        return
    requests.post(DISCORD_WEBHOOK, json={"content": message}, timeout=10)
    mark_discord_sent()

# Reuse session for speed
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

def get_soup(url):
    r = SESSION.get(url, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def load_seen_items():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f)

def save_seen_items(items):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for i in sorted(items):
            f.write(i + "\n")

def looks_in_stock(text):
    t = text.lower()
    return not any(x in t for x in [
        "out of stock", "sold out", "unavailable", "no longer available"
    ])

# ================= SAFE PARSER =================

def safe_parse(parser, url):
    try:
        return parser(url)
    except Exception as e:
        print(f"Parser error ({url}): {e}")
        return []

# ================= PARSERS =================
# (Same as your previous code; each parser uses get_soup)
# parse_smyths, parse_entertainer, parse_onestop, parse_whsmith, 
# parse_forbidden_planet, parse_waterstones, parse_cex, generic_parser

# ================= STORES =================
# Use per-store radius for physical stores
# Online stores: "online": True, skip radius check
STORES = {
    "Smyths Toys": {"url": "https://www.smythstoys.com/uk/en-gb/search/?text=pokemon", "coord": (53.552, -1.128), "radius": 25, "parser": parse_smyths, "online": False},
    "The Entertainer": {"url": "https://www.thetoyshop.com/search/?text=pokemon", "coord": (53.521, -1.120), "radius": 30, "parser": parse_entertainer, "online": False},
    "One Stop": {"url": "https://www.onestop.co.uk/search?query=pokemon", "coord": USER_COORD, "radius": 30, "parser": parse_onestop, "online": False},
    "WHSmith": {"url": "https://www.whsmith.co.uk/search?query=pokemon", "coord": (53.518, -1.121), "radius": 30, "parser": parse_whsmith, "online": False},
    "Forbidden Planet": {"url": "https://forbiddenplanet.com/catalogsearch/result/?q=pokemon", "coord": USER_COORD, "radius": 30, "parser": parse_forbidden_planet, "online": False},
    "Waterstones": {"url": "https://www.waterstones.com/books/search/term/pokemon", "coord": USER_COORD, "radius": 30, "parser": parse_waterstones, "online": False},
    "CEX": {"url": "https://uk.webuy.com/search/?query=pokemon", "coord": USER_COORD, "radius": 30, "parser": parse_cex, "online": False},

    "Amazon UK": {"url": "https://www.amazon.co.uk/s?k=pokemon+tcg", "parser": generic_parser, "online": True},
    "eBay UK": {"url": "https://www.ebay.co.uk/sch/i.html?_nkw=pokemon+tcg", "parser": generic_parser, "online": True},
    "ASDA": {"url": "https://groceries.asda.com/search/pokemon", "parser": generic_parser, "online": True},
    "Tesco": {"url": "https://www.tesco.com/groceries/en-GB/search?query=pokemon", "parser": generic_parser, "online": True},
    "Morrisons": {"url": "https://groceries.morrisons.com/search?searchTerm=pokemon", "parser": generic_parser, "online": True},
    "Sainsbury's": {"url": "https://www.sainsburys.co.uk/shop/gb/groceries/search?search-term=pokemon", "parser": generic_parser, "online": True},
    "Aldi": {"url": "https://www.aldi.co.uk/search?query=pokemon", "parser": generic_parser, "online": True},
    "B&M": {"url": "https://www.bmstores.co.uk/brands/pok-mon", "parser": generic_parser, "online": True},
}

# ================= MAIN =================

def fetch_store(store, cfg):
    try:
        if not cfg.get("online") and not within_distance(cfg["coord"], cfg.get("radius", DEFAULT_RADIUS_MILES)):
            return store, []
        products = safe_parse(cfg["parser"], cfg["url"])
        return store, products
    except Exception as e:
        print(f"{store} error: {e}")
        return store, []

def run():
    seen_items = load_seen_items()
    updated_seen = set(seen_items)
    notifications = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(lambda s: fetch_store(s[0], s[1]), STORES.items())

    for store, products in results:
        for product in products:
            if not looks_in_stock(product["name"]):
                continue
            uid = f"{store}:{product['name']}"
            if uid in seen_items:
                continue
            updated_seen.add(uid)
            notifications.append((store, product))

    if notifications:
        message = f"POKEMON RESTOCK ({USER_LOCATION_LABEL})\n\n"
        for store, p in notifications[:20]:  # Show up to 20 items per message
            message += f"{store}: {p['name']} ({p['price']})\n{p['link']}\n\n"
        send_discord(message)

    save_seen_items(updated_seen)

if __name__ == "__main__":
    run()

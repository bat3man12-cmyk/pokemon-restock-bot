import os
import time
import requests
from bs4 import BeautifulSoup
from geopy.distance import geodesic

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

def get_soup(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
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
        "out of stock",
        "sold out",
        "unavailable",
        "no longer available"
    ])

# ================= PARSERS (FAIL-SAFE) =================

def safe_parse(parser, url):
    try:
        return parser(url)
    except Exception as e:
        print(f"Parser error ({url}): {e}")
        return []

def generic_parser(url):
    soup = get_soup(url)
    products = []
    for a in soup.select("a"):
        name = a.get_text(strip=True)
        if not name or "pokemon" not in name.lower():
            continue
        if not is_sealed(name):
            continue
        link = a.get("href") or url
        full = link if link.startswith("http") else url
        products.append({
            "name": name,
            "price": "Check website",
            "link": full
        })
    return products

# ================= STORES =================

STORES = {
    # Physical stores
    "Smyths Toys": {
        "url": "https://www.smythstoys.com/uk/en-gb/search/?text=pokemon",
        "coord": (53.552, -1.128),
        "radius": 25,
        "parser": generic_parser,
        "online": False,
    },
    "The Entertainer": {
        "url": "https://www.thetoyshop.com/search/?text=pokemon",
        "coord": (53.521, -1.120),
        "radius": 30,
        "parser": generic_parser,
        "online": False,
    },

    # Online stores
    "Amazon UK": {
        "url": "https://www.amazon.co.uk/s?k=pokemon+tcg",
        "parser": generic_parser,
        "online": True,
    },
    "eBay UK": {
        "url": "https://www.ebay.co.uk/sch/i.html?_nkw=pokemon+tcg",
        "parser": generic_parser,
        "online": True,
    },
}

# ================= MAIN =================

def run():
    seen = load_seen_items()
    updated_seen = set(seen)
    notifications = []

    for store, cfg in STORES.items():
        try:
            # Distance check only for physical stores
            if not cfg.get("online"):
                radius = cfg.get("radius", DEFAULT_RADIUS_MILES)
                if not within_distance(cfg["coord"], radius):
                    continue

            products = safe_parse(cfg["parser"], cfg["url"])
            for p in products:
                if not looks_in_stock(p["name"]):
                    continue

                uid = f"{store}:{p['name']}"
                if uid in seen:
                    continue

                updated_seen.add(uid)
                notifications.append((store, p))

        except Exception as e:
            print(f"{store} error: {e}")

    if notifications:
        message = f"POKEMON RESTOCK ({USER_LOCATION_LABEL})\n\n"
        for store, p in notifications[:10]:
            message += (
                f"{store}\n"
                f"- {p['name']}\n"
                f"  {p['price']}\n"
                f"  {p['link']}\n\n"
            )
        send_discord(message)

    save_seen_items(updated_seen)

if __name__ == "__main__":
    run()

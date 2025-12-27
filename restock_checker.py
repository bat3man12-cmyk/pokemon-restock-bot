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
    "booster", "elite trainer box", "etb", "tin",
    "collection", "blister", "trading card",
]

IGNORE_KEYWORDS = [
    "single", "guide", "book", "magazine", "proxy",
]

# ================= STORE COLORS =================

STORE_COLORS = {
    "Smyths Toys": 0x1E90FF,
    "The Entertainer": 0x32CD32,
    "One Stop": 0xFFD700,
    "WHSmith": 0x8A2BE2,
    "Forbidden Planet": 0xFF4500,
    "Waterstones": 0x00CED1,
    "CEX": 0xFF69B4,
    "Amazon UK": 0xFF9900,
    "eBay UK": 0xE53238,
    "ASDA": 0x006400,
    "Tesco": 0x0051BA,
    "Morrisons": 0xFFD700,
    "Sainsbury's": 0xFFA500,
    "Aldi": 0x003087,
    "B&M": 0xFF0000,
}

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

def send_discord_embeds(embeds: list):
    if not can_send_discord():
        return
    payload = {"embeds": embeds}
    requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
    mark_discord_sent()

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
    return not any(x in t for x in ["out of stock", "sold out", "unavailable", "no longer available"])

def safe_parse(parser, url):
    try:
        return parser(url)
    except Exception as e:
        print(f"Parser error ({url}): {e}")
        return []

# ================= PRODUCT EMOJI =================

def product_emoji(name: str) -> str:
    name = name.lower()
    if "booster" in name:
        return "🎴"
    elif "elite trainer box" in name or "etb" in name:
        return "📦"
    elif "tin" in name or "collection" in name:
        return "🛍️"
    elif "blister" in name or "trading card" in name:
        return "🃏"
    else:
        return "✨"

# ================= PARSERS =================

def parse_smyths(url):
    soup = get_soup(url)
    products = []
    for tile in soup.select("div.product-tile"):
        name_el = tile.select_one("h2.product-name")
        price_el = tile.select_one("span.price")
        link_el = tile.select_one("a")
        if not name_el or not link_el:
            continue
        name = name_el.text.strip()
        if not is_sealed(name):
            continue
        products.append({
            "name": name,
            "price": price_el.text.strip() if price_el else "Price unavailable",
            "link": "https://www.smythstoys.com" + link_el["href"]
        })
    return products

def parse_entertainer(url):
    soup = get_soup(url)
    products = []
    for item in soup.select("div.product-item"):
        name_el = item.select_one("a.product-name")
        price_el = item.select_one("span.value")
        if not name_el:
            continue
        name = name_el.text.strip()
        if not is_sealed(name):
            continue
        products.append({
            "name": name,
            "price": price_el.text.strip() if price_el else "Price unavailable",
            "link": "https://www.thetoyshop.com" + name_el["href"]
        })
    return products

def parse_onestop(url):
    soup = get_soup(url)
    products = []
    for item in soup.select("a"):
        name = item.get_text(strip=True)
        link = item.get("href")
        if not name or not link or "pokemon" not in name.lower() or not is_sealed(name):
            continue
        price = "Check local store"
        parent = item.parent
        if parent:
            price_el = parent.find(text=lambda t: t and "£" in t)
            if price_el:
                price = price_el.strip()
        full_link = link if link.startswith("http") else "https://www.onestop.co.uk" + link
        products.append({"name": name, "price": price, "link": full_link})
    return products

def parse_whsmith(url):
    soup = get_soup(url)
    products = []
    for p in soup.select("h3"):
        name = p.text.strip()
        if not is_sealed(name):
            continue
        products.append({"name": name, "price": "Check website", "link": url})
    return products

def parse_forbidden_planet(url):
    soup = get_soup(url)
    products = []
    for p in soup.select("h3.product-title"):
        name = p.text.strip()
        if not is_sealed(name):
            continue
        products.append({"name": name, "price": "Check website", "link": url})
    return products

def parse_waterstones(url):
    soup = get_soup(url)
    products = []
    for a in soup.select("a.title"):
        name = a.text.strip()
        if not is_sealed(name):
            continue
        link = a.get("href") or url
        full_link = link if link.startswith("http") else "https://www.waterstones.com" + link
        products.append({"name": name, "price": "Check website", "link": full_link})
    return products

def parse_cex(url):
    soup = get_soup(url)
    products = []
    for p in soup.select("h3"):
        name = p.text.strip()
        if not is_sealed(name):
            continue
        products.append({"name": name, "price": "Check website", "link": url})
    return products

def generic_parser(url):
    soup = get_soup(url)
    products = []
    for a in soup.select("a"):
        name = a.get_text(strip=True)
        href = a.get("href") or url
        if not name or "pokemon" not in name.lower() or not is_sealed(name):
            continue
        full_link = href if href.startswith("http") else url
        products.append({"name": name, "price": "Check website", "link": full_link})
    return products

# ================= STORES =================

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
        store_map = {}
        for store, p in notifications[:50]:
            emoji = product_emoji(p['name'])
            info = f"{emoji} {p['name']}\nPrice: `{p['price']}`\n[Link]({p['link']})"
            store_map.setdefault(store, []).append(info)

        embeds = []

        # Summary embed
        embeds.append({
            "title": f"⚡ POKEMON RESTOCK ALERT! ⚡",
            "description": f"📍 Location: {USER_LOCATION_LABEL}\n🆕 Total new items: **{len(notifications)}**",
            "color": 0xFF4500,
            "footer": {"text": "Check stores quickly, restocks go fast!"}
        })

        # Per-store embeds (only stores with new items)
        for store, items in store_map.items():
            if not items:
                continue
            embeds.append({
                "title": f"{store} Restock ({len(items)} new items)",
                "description": "\n\n".join(items),
                "color": STORE_COLORS.get(store, 0xFF0000),
                "footer": {"text": f"📍 Location: {USER_LOCATION_LABEL} - Check stores quickly!"}
            })

        send_discord_embeds(embeds)

    save_seen_items(updated_seen)

if __name__ == "__main__":
    run()

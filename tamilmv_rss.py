import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, ElementTree
import time, json, os
from urllib.parse import parse_qs, urlparse

# ================= CONFIG =================
BASE_URLS = [
    "https://www.1tamilmv.haus/",
    "https://www.1tamilmv.lc/"
]

OUT_FILE = "tamilmv.xml"
STATE_FILE = "state.json"

MAX_SIZE_GB = 4              # ⛔ Skip >4GB
TOPIC_LIMIT = 10             # Latest topics only
TOPIC_DELAY = 5              # Seconds between topic fetch
MAX_MAGNETS_PER_RUN = 15     # 🚑 Flood control
# ==========================================

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)

# ---------------- Load state ----------------
if os.path.exists(STATE_FILE):
    with open(STATE_FILE) as f:
        state = json.load(f)
else:
    state = {"magnets": []}

processed = set(state.get("magnets", []))

# ---------------- Resolve working domain ----------------
BASE_URL = None
for url in BASE_URLS:
    try:
        r = scraper.get(url, timeout=20)
        if r.status_code == 200:
            BASE_URL = url
            break
    except:
        continue

if not BASE_URL:
    print("❌ No working domain")
    exit()

print("✅ Using:", BASE_URL)

# ---------------- RSS setup ----------------
rss = Element("rss", version="2.0")
channel = SubElement(rss, "channel")

SubElement(channel, "title").text = "1TamilMV Torrent RSS"
SubElement(channel, "link").text = BASE_URL
SubElement(channel, "description").text = "Auto Torrent RSS (Below 4GB)"
SubElement(channel, "lastBuildDate").text = datetime.utcnow().strftime(
    "%a, %d %b %Y %H:%M:%S GMT"
)

# ---------------- Fetch homepage ----------------
home = scraper.get(BASE_URL, timeout=30)
soup = BeautifulSoup(home.text, "lxml")

posts = []
for a in soup.select("a[href*='forums/topic']"):
    # ❌ skip pinned topics
    if "pinned" in a.get("class", []):
        continue
    posts.append((a.get_text(strip=True), a["href"]))

posts = posts[:TOPIC_LIMIT]

def magnet_size_gb(magnet):
    qs = parse_qs(urlparse(magnet).query)
    if "xl" in qs:
        return int(qs["xl"][0]) / (1024 ** 3)
    return None

# ---------------- Scrape topics ----------------
added_count = 0
new_data = False

for title, post_url in posts:
    if added_count >= MAX_MAGNETS_PER_RUN:
        print("🚑 Flood limit reached")
        break

    try:
        time.sleep(TOPIC_DELAY)
        page = scraper.get(post_url, timeout=30)
        psoup = BeautifulSoup(page.text, "lxml")

        for a in psoup.find_all("a", href=True):
            magnet = a["href"]

            if not magnet.startswith("magnet:?"):
                continue

            if magnet in processed:
                continue

            size = magnet_size_gb(magnet)
            if size and size > MAX_SIZE_GB:
                continue

            item = SubElement(channel, "item")
            SubElement(item, "title").text = (
                f"{title} [{round(size,2)}GB]" if size else title
            )
            SubElement(item, "link").text = magnet
            SubElement(item, "guid").text = magnet
            SubElement(item, "pubDate").text = datetime.utcnow().strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )

            processed.add(magnet)
            added_count += 1
            new_data = True
            print("➕", title, size)

            if added_count >= MAX_MAGNETS_PER_RUN:
                break

    except Exception as e:
        print("ERROR:", title, e)

# ---------------- Save RSS ----------------
if new_data:
    ElementTree(rss).write(OUT_FILE, encoding="utf-8", xml_declaration=True)
    print("✅ RSS UPDATED")
else:
    print("ℹ️ No new torrents")

with open(STATE_FILE, "w") as f:
    json.dump({"magnets": list(processed)}, f, indent=2)

print("DONE")

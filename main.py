import cloudscraper
import re
import time

ANIME_SAMA_URL = "https://anime-sama.eu"
DELAY = 1

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "desktop": True}
)

def get_page(url):
    r = scraper.get(url, timeout=30)
    time.sleep(DELAY)
    return r.text if r.status_code == 200 else ""

def count_animes_only():
    page = 1
    total = 0

    while True:
        url = f"{ANIME_SAMA_URL}/catalogue/?page={page}" if page > 1 else f"{ANIME_SAMA_URL}/catalogue/"
        print(f"📖 Analyse page {page}...")
        html = get_page(url)

        if not html:
            break

        # cartes du catalogue
        cards = re.findall(
            r'<div class="shrink-0 catalog-card card-base">(.*?)</div>\s*</div>\s*</a>\s*</div>',
            html,
            re.DOTALL
        )

        if not cards:
            break

        page_count = 0

        for card in cards:
            types_match = re.search(
                r'<span class="info-label">Types</span>\s*<p class="info-value">([^<]*)</p>',
                card
            )
            types = types_match.group(1) if types_match else ""

            if "Anime" in types:
                total += 1
                page_count += 1

        print(f"   ➜ {page_count} animes trouvés")

        if f'page={page + 1}' not in html:
            break

        page += 1

    return total

if __name__ == "__main__":
    total_animes = count_animes_only()
    print("\n==============================")
    print(f"🎬 TOTAL ANIMES (sans scans) : {total_animes}")
    print("==============================")

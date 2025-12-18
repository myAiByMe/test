#!/usr/bin/env python3
"""
Scraper complet pour Anime-Sama
Génère des fichiers JSON avec tous les animes, saisons, épisodes et URLs
"""

import cloudscraper
import re
import json
import time
from pathlib import Path
from typing import List, Dict, Any
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
ANIME_SAMA_URL = "https://anime-sama.eu"
OUTPUT_DIR = Path("scraped_data")
DELAY_BETWEEN_REQUESTS = 2  # Secondes entre chaque requête

# Créer le dossier de sortie
OUTPUT_DIR.mkdir(exist_ok=True)

# Initialiser cloudscraper
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

def get_page(url: str, retries=3) -> str:
    """Récupère une page avec retry en cas d'échec"""
    for attempt in range(retries):
        try:
            logger.info(f"Fetching: {url} (attempt {attempt + 1}/{retries})")
            response = scraper.get(url, timeout=30)
            if response.status_code == 200:
                time.sleep(DELAY_BETWEEN_REQUESTS)
                return response.text
            logger.warning(f"Status {response.status_code} for {url}")
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            if attempt < retries - 1:
                time.sleep(5)
    return ""

def extract_catalogue_animes(html: str) -> List[Dict[str, Any]]:
    """Extrait tous les animes depuis une page catalogue"""
    animes = []
    
    # Pattern pour capturer chaque carte
    card_pattern = r'<div class="shrink-0 catalog-card card-base">(.*?)</div>\s*</div>\s*</a>\s*</div>'
    cards = re.findall(card_pattern, html, re.DOTALL)
    
    for card in cards:
        try:
            # URL
            url_match = re.search(r'<a href="([^"]+)">', card)
            if not url_match:
                continue
            url = url_match.group(1)
            
            # Image
            image_match = re.search(r'<img[^>]+src="([^"]+)"', card)
            image = image_match.group(1) if image_match else ""
            
            # Titre
            title_match = re.search(r'<h2 class="card-title">([^<]+)</h2>', card)
            if not title_match:
                continue
            title = title_match.group(1).strip()
            
            # Noms alternatifs
            alt_match = re.search(r'<p class="alternate-titles">([^<]*)</p>', card)
            alt_names = alt_match.group(1).strip() if alt_match else ""
            
            # Genres
            genres_match = re.search(r'<span class="info-label">Genres</span>\s*<p class="info-value">([^<]*)</p>', card)
            genres = genres_match.group(1).strip() if genres_match else ""
            
            # Types
            types_match = re.search(r'<span class="info-label">Types</span>\s*<p class="info-value">([^<]*)</p>', card)
            types = types_match.group(1).strip() if types_match else ""
            
            # Langues
            langs_match = re.search(r'<span class="info-label">Langues</span>\s*<p class="info-value">([^<]*)</p>', card)
            languages = langs_match.group(1).strip() if langs_match else ""
            
            # Ne garder que les animes (pas les scans)
            if "Anime" not in types:
                continue
            
            animes.append({
                'url': url,
                'title': title,
                'alt_names': alt_names,
                'image': image,
                'genres': [g.strip() for g in genres.split(", ") if g],
                'languages': [l.strip() for l in languages.split(", ") if l]
            })
            
        except Exception as e:
            logger.error(f"Error parsing card: {e}")
            continue
    
    return animes

def get_all_animes_from_catalogue() -> List[Dict[str, Any]]:
    """Récupère tous les animes du catalogue (toutes les pages)"""
    all_animes = []
    page = 1
    
    while True:
        logger.info(f"Scraping catalogue page {page}...")
        url = f"{ANIME_SAMA_URL}/catalogue/?page={page}" if page > 1 else f"{ANIME_SAMA_URL}/catalogue/"
        html = get_page(url)
        
        if not html:
            break
        
        animes = extract_catalogue_animes(html)
        if not animes:
            break
        
        all_animes.extend(animes)
        logger.info(f"Found {len(animes)} animes on page {page}")
        
        # Vérifier s'il y a une page suivante
        if f'page={page + 1}' not in html:
            break
        
        page += 1
    
    logger.info(f"Total animes found: {len(all_animes)}")
    return all_animes

def extract_seasons_from_anime_page(html: str, base_url: str) -> List[Dict[str, str]]:
    """Extrait les saisons depuis la page d'un anime"""
    seasons = []
    
    # Pattern pour panneauAnime et panneauScan
    pattern = r'panneau(?:Anime|Scan)\("([^"]+)",\s*"([^"]+)"\);'
    matches = re.findall(pattern, html)
    
    for name, link in matches:
        # Ne garder que les animes (pas les scans)
        if 'Scan' not in name and 'scan' not in link:
            # Nettoyer le lien (enlever / au début et à la fin)
            clean_link = link.strip('/')
            
            # Enlever "url" du lien si présent (ex: "url" -> "")
            clean_link = clean_link.replace('url', '')
            
            # Enlever les langues du lien si elles sont présentes (car on les ajoutera nous-mêmes)
            clean_link = clean_link.replace('/vostfr', '').replace('/vf', '')
            
            # Nettoyer les slashes multiples ou en début/fin
            clean_link = clean_link.strip('/')
            
            # Construire l'URL correcte (sans langue, on l'ajoutera dans get_episodes_from_season)
            if not base_url.endswith('/'):
                base_url += '/'
            
            # Si clean_link est vide, utiliser juste base_url
            if clean_link:
                full_url = f"{base_url}{clean_link}/"
            else:
                full_url = base_url
            
            seasons.append({
                'name': name,
                'url': full_url
            })
    
    return seasons

def extract_synopsis(html: str) -> str:
    """Extrait le synopsis"""
    match = re.search(r'<h2[^>]*>Synopsis</h2>\s*<p[^>]*>([^<]+)</p>', html, re.DOTALL)
    return match.group(1).strip() if match else ""

def get_episodes_from_season(season_url: str) -> List[Dict[str, Any]]:
    """Récupère tous les épisodes d'une saison avec toutes les langues"""
    episodes_data = {}
    
    # Langues à checker
    languages = ['vostfr', 'vf']
    
    for lang in languages:
        # Construire l'URL correctement (season_url se termine déjà par /)
        lang_url = f"{season_url}{lang}/"
        html = get_page(lang_url)
        
        if not html:
            continue
        
        # Trouver le fichier episodes.js
        js_match = re.search(r"episodes\.js\?filever=\d+", html)
        if not js_match:
            continue
        
        # Récupérer le fichier episodes.js
        js_url = lang_url + js_match.group(0)
        js_content = get_page(js_url)
        
        if not js_content:
            continue
        
        # Extraire les épisodes (eps1, eps2, etc.)
        eps_pattern = r'var eps(\d+) = \[(.*?)\];'
        eps_matches = re.findall(eps_pattern, js_content, re.DOTALL)
        
        for player_num, urls_str in eps_matches:
            # Extraire toutes les URLs
            urls = re.findall(r"'([^']+)'", urls_str)
            
            # Pour chaque URL (= un épisode)
            for ep_num, url in enumerate(urls, 1):
                if ep_num not in episodes_data:
                    episodes_data[ep_num] = {
                        'episode_number': ep_num,
                        'title': f"Episode {ep_num}",
                        'description': "",
                        'duration': 0,
                        'languages': [],
                        'urls': {}
                    }
                
                # Ajouter la langue si pas déjà présente
                lang_upper = lang.upper()
                if lang_upper not in episodes_data[ep_num]['languages']:
                    episodes_data[ep_num]['languages'].append(lang_upper)
                
                # Ajouter l'URL
                if lang_upper not in episodes_data[ep_num]['urls']:
                    episodes_data[ep_num]['urls'][lang_upper] = []
                
                episodes_data[ep_num]['urls'][lang_upper].append(url)
    
    # Convertir en liste et mettre la meilleure URL par langue
    episodes = []
    for ep_num in sorted(episodes_data.keys()):
        ep = episodes_data[ep_num]
        
        # Pour chaque langue, garder toutes les URLs mais mettre Vidmoly en premier
        for lang in ep['urls']:
            urls = ep['urls'][lang]
            # Trier: Vidmoly en premier, puis autres
            vidmoly = [u for u in urls if 'vidmoly' in u.lower()]
            others = [u for u in urls if 'vidmoly' not in u.lower()]
            ep['urls'][lang] = vidmoly + others
        
        episodes.append(ep)
    
    return episodes

def scrape_anime_details(anime_info: Dict[str, Any], anime_id: int) -> Dict[str, Any]:
    """Scrape les détails complets d'un anime"""
    logger.info(f"Scraping anime: {anime_info['title']}")
    
    html = get_page(anime_info['url'])
    if not html:
        return None
    
    # Extraire le synopsis
    synopsis = extract_synopsis(html)
    
    # Extraire les saisons
    seasons_info = extract_seasons_from_anime_page(html, anime_info['url'])
    
    seasons = []
    for i, season_info in enumerate(seasons_info, 1):
        logger.info(f"  Scraping season: {season_info['name']}")
        
        # Déterminer le numéro de saison
        season_num_match = re.search(r'(?:Saison|Season)\s*(\d+)', season_info['name'], re.IGNORECASE)
        season_number = int(season_num_match.group(1)) if season_num_match else i
        
        # Cas spécial pour les films
        if 'Film' in season_info['name'] or 'Movie' in season_info['name']:
            season_number = 99
        
        # Récupérer les épisodes
        episodes = get_episodes_from_season(season_info['url'])
        
        if episodes:
            seasons.append({
                'season_number': season_number,
                'name': season_info['name'],
                'episodes': episodes
            })
            logger.info(f"    Found {len(episodes)} episodes")
    
    return {
        'id': anime_id,
        'anime_id': anime_id,
        'title': anime_info['title'],
        'original_title': anime_info['title'],
        'description': synopsis or "Description non disponible",
        'image': anime_info['image'],
        'image_url': anime_info['image'],
        'genres': anime_info['genres'],
        'seasons': seasons,
        'featured': False,
        'year': '',
        'status': 'Disponible',
        'rating': 7.5,
        'languages': anime_info['languages'],
        'seasons_fetched': True,
        'has_episodes': len(seasons) > 0
    }

def save_animes_by_letter(animes: List[Dict[str, Any]]):
    """Sauvegarde les animes dans des fichiers par lettre"""
    # Grouper par première lettre
    by_letter = {}
    for anime in animes:
        first_letter = anime['title'][0].upper()
        if not first_letter.isalpha():
            first_letter = '#'  # Pour les nombres et symboles
        
        if first_letter not in by_letter:
            by_letter[first_letter] = []
        by_letter[first_letter].append(anime)
    
    # Sauvegarder chaque lettre
    for letter, letter_animes in by_letter.items():
        output_file = OUTPUT_DIR / f"animes_{letter}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(letter_animes, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(letter_animes)} animes to {output_file}")
    
    # Sauvegarder aussi un fichier complet
    output_file = OUTPUT_DIR / "animes_all.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(animes, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(animes)} total animes to {output_file}")
    
    # Créer un index
    index = {
        'total': len(animes),
        'by_letter': {letter: len(letter_animes) for letter, letter_animes in by_letter.items()},
        'letters': sorted(by_letter.keys())
    }
    
    index_file = OUTPUT_DIR / "index.json"
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved index to {index_file}")

def main():
    """Fonction principale"""
    logger.info("=== Anime-Sama Scraper ===")
    logger.info(f"Output directory: {OUTPUT_DIR.absolute()}")
    
    # Étape 1: Récupérer tous les animes du catalogue
    logger.info("\n[1/3] Fetching all animes from catalogue...")
    catalogue_animes = get_all_animes_from_catalogue()
    
    if not catalogue_animes:
        logger.error("No animes found in catalogue!")
        return
    
    # Étape 2: Scraper les détails de chaque anime
    logger.info(f"\n[2/3] Scraping details for {len(catalogue_animes)} animes...")
    scraped_animes = []
    
    for i, anime_info in enumerate(catalogue_animes, 1):
        try:
            logger.info(f"\nProgress: {i}/{len(catalogue_animes)}")
            anime_data = scrape_anime_details(anime_info, i)
            
            if anime_data:
                scraped_animes.append(anime_data)
            
            # Sauvegarder progressivement tous les 10 animes
            if i % 10 == 0:
                logger.info(f"Saving checkpoint... ({len(scraped_animes)} animes)")
                save_animes_by_letter(scraped_animes)
        
        except KeyboardInterrupt:
            logger.warning("\nInterrupted by user!")
            break
        except Exception as e:
            logger.error(f"Error scraping {anime_info['title']}: {e}")
            continue
    
    # Étape 3: Sauvegarder tous les résultats
    logger.info(f"\n[3/3] Saving {len(scraped_animes)} animes...")
    save_animes_by_letter(scraped_animes)
    
    logger.info("\n=== Scraping completed! ===")
    logger.info(f"Total animes scraped: {len(scraped_animes)}")
    logger.info(f"Files saved in: {OUTPUT_DIR.absolute()}")

if __name__ == "__main__":
    main()
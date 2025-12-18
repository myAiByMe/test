"""
Application Flask complète pour AnimeZone avec système de segmentation vidéo
"""

import os
import json
import logging
import datetime
import re
import m3u8
import requests
from urllib.parse import urljoin
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialisation des extensions
db = SQLAlchemy()
login_manager = LoginManager()

# Session pour les requêtes vidéo
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
video_session = requests.Session()
video_session.headers.update({'User-Agent': USER_AGENT})

# ==================
# MODÈLES DE DONNÉES
# ==================

class User(UserMixin, db.Model):
    """Modèle utilisateur"""
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    last_login = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class UserProgress(db.Model):
    """Modèle pour suivre la progression des utilisateurs"""
    __tablename__ = 'user_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    anime_id = db.Column(db.Integer, nullable=False)
    season_number = db.Column(db.Integer, nullable=False)
    episode_number = db.Column(db.Integer, nullable=False)
    time_position = db.Column(db.Float, default=0)
    completed = db.Column(db.Boolean, default=False)
    last_watched = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    user = db.relationship('User', backref=db.backref('progress', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'anime_id', 'season_number', 'episode_number'),
    )


class UserFavorite(db.Model):
    """Modèle pour les favoris des utilisateurs"""
    __tablename__ = 'user_favorite'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    anime_id = db.Column(db.Integer, nullable=False)
    added_at = db.Column(db.DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))

    user = db.relationship('User', backref=db.backref('favorites', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'anime_id'),
    )


# ==================
# SYSTÈME DE SEGMENTATION VIDÉO
# ==================

def parse_video_url(url):
    """Parse l'URL et retourne (type, video_id)"""
    url_lower = url.lower()
    
    if 'vidmoly' in url_lower:
        match = re.search(r'embed-([a-zA-Z0-9]+)\.html', url)
        return ('vidmoly', match.group(1)) if match else (None, None)
    
    if 'sibnet' in url_lower:
        match = re.search(r'videoembed/(\d+)', url)
        return ('sibnet', match.group(1)) if match else (None, None)
    
    if 'sendvid' in url_lower:
        match = re.search(r'embed/([a-zA-Z0-9]+)', url)
        return ('sendvid', match.group(1)) if match else (None, None)
    
    return None, None


def extract_vidmoly_m3u8(embed_url):
    """Extrait l'URL M3U8 depuis Vidmoly"""
    try:
        response = video_session.get(embed_url, timeout=10)
        html = response.text
        
        pattern = r'sources\s*:\s*\[\s*{\s*file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']'
        match = re.search(pattern, html, re.IGNORECASE)
        
        if match:
            return match.group(1)
        
        pattern2 = r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']'
        match = re.search(pattern2, html, re.IGNORECASE)
        
        return match.group(1) if match else None
    except:
        return None


def extract_sibnet_m3u8(embed_url):
    """Extrait l'URL M3U8 depuis Sibnet"""
    try:
        response = video_session.get(embed_url, timeout=10)
        html = response.text
        
        # Pattern pour Sibnet
        pattern = r'player\.src\(\[\{[^}]*src:\s*["\']([^"\']+\.m3u8[^"\']*)["\']'
        match = re.search(pattern, html, re.IGNORECASE)
        
        if match:
            return match.group(1)
        
        # Pattern alternatif
        pattern2 = r'["\']([^"\']*video\.sibnet\.ru[^"\']*\.m3u8[^"\']*)["\']'
        match = re.search(pattern2, html, re.IGNORECASE)
        
        return match.group(1) if match else None
    except:
        return None


def get_hls_segments(master_url):
    """Récupère la liste des segments HLS"""
    try:
        response = video_session.get(master_url, timeout=10)
        master = m3u8.loads(response.text)
        
        if master.segments:
            return master_url, master
        
        if master.playlists:
            base_url = master_url.rsplit('/', 1)[0] + '/'
            playlist_url = urljoin(base_url, master.playlists[-1].uri)
            
            response = video_session.get(playlist_url, timeout=10)
            playlist = m3u8.loads(response.text)
            
            return playlist_url, playlist
        
        return None, None
    except:
        return None, None


def extract_sendvid_video(embed_url):
    """Extrait l'URL MP4 depuis SendVid"""
    try:
        response = video_session.get(embed_url, timeout=10)
        html = response.text
        
        pattern1 = r'<source[^>]*src=["\']([^"\']+\.mp4[^"\']*)["\']'
        match = re.search(pattern1, html, re.IGNORECASE)
        if match:
            url = match.group(1)
            return url if url.startswith('http') else urljoin('https://sendvid.com', url)
        
        pattern2 = r'file\s*:\s*["\']([^"\']+\.(mp4|webm)[^"\']*)["\']'
        match = re.search(pattern2, html, re.IGNORECASE)
        if match:
            url = match.group(1)
            return url if url.startswith('http') else urljoin('https://sendvid.com', url)
        
        return None
    except:
        return None


# ==================
# UTILITAIRES
# ==================

def load_anime_data():
    """Charge les données des animes depuis le fichier JSON local"""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, 'static', 'data', 'anime.json')
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            animes = data.get('anime', data) if isinstance(data, dict) else data
            
            for anime in animes:
                if 'anime_id' not in anime:
                    anime['anime_id'] = anime.get('id', 0)
                if 'has_episodes' not in anime:
                    anime['has_episodes'] = len(anime.get('seasons', [])) > 0
            
            return animes
    except Exception as e:
        logger.error(f"Erreur chargement anime.json: {e}")
        return []


def load_discover_data():
    """Charge les animes de découverte"""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, 'data_discover.json')
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else data.get('anime', [])
    except Exception as e:
        logger.error(f"Erreur chargement data_discover.json: {e}")
        return []


def get_all_genres():
    """Extrait tous les genres uniques"""
    anime_data = load_anime_data()
    genres = set()
    for anime in anime_data:
        for genre in anime.get('genres', []):
            genres.add(genre.lower())
    return sorted(list(genres))


# ==================
# FACTORY D'APPLICATION
# ==================

def create_app():
    """Factory pour créer l'application Flask"""
    app = Flask(__name__)
    
    # Configuration
    app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key_123")
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///anime.db"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialiser les extensions avec l'app
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    # User loader pour Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))
    
    # Créer les tables
    with app.app_context():
        db.create_all()
        logger.info("✅ Base de données initialisée")
    
    # ==================
    # ROUTES PRINCIPALES
    # ==================
    
    @app.route('/')
    def index():
        """Page d'accueil"""
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        
        anime_data = load_anime_data()
        
        # Animes en cours de visionnage
        continue_watching = []
        if current_user.is_authenticated:
            try:
                latest_progress = UserProgress.query.filter_by(
                    user_id=current_user.id
                ).order_by(UserProgress.last_watched.desc()).all()
                
                processed = set()
                for progress in latest_progress:
                    if progress.anime_id not in processed and len(continue_watching) < 20:
                        anime = next((a for a in anime_data if int(a.get('id', 0)) == progress.anime_id), None)
                        if anime:
                            season = next((s for s in anime.get('seasons', []) 
                                         if s.get('season_number') == progress.season_number), None)
                            if season:
                                episode = next((e for e in season.get('episodes', []) 
                                              if e.get('episode_number') == progress.episode_number), None)
                                if episode:
                                    continue_watching.append({
                                        'anime': anime,
                                        'progress': progress,
                                        'season': season,
                                        'episode': episode
                                    })
                                    processed.add(progress.anime_id)
            except Exception as e:
                logger.error(f"Erreur progression: {e}")
        
        # Favoris
        favorite_anime = []
        if current_user.is_authenticated:
            try:
                favorites = UserFavorite.query.filter_by(user_id=current_user.id).all()
                for fav in favorites[:15]:
                    anime = next((a for a in anime_data if a.get('id') == fav.anime_id), None)
                    if anime:
                        favorite_anime.append(anime)
            except Exception as e:
                logger.error(f"Erreur favoris: {e}")
        
        # Animes en vedette
        featured = load_discover_data()
        featured = [a for a in featured if a.get('has_episodes', False)][:12]
        
        return render_template('index_new.html',
                              anime_list=featured,
                              continue_watching=continue_watching,
                              favorite_anime=favorite_anime)
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Page de connexion"""
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username).first()
            
            if user and user.check_password(password):
                user.last_login = datetime.datetime.now(datetime.timezone.utc)
                db.session.commit()
                login_user(user)
                next_page = request.args.get('next')
                return redirect(next_page if next_page else url_for('index'))
            
            flash('Nom d\'utilisateur ou mot de passe incorrect', 'danger')
        
        return render_template('login_new.html')
    
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        """Page d'inscription"""
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            confirm = request.form.get('confirm_password')
            
            if password != confirm:
                flash('Les mots de passe ne correspondent pas', 'danger')
            elif User.query.filter_by(username=username).first():
                flash('Nom d\'utilisateur déjà pris', 'danger')
            else:
                user = User(username=username)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash('Compte créé avec succès!', 'success')
                return redirect(url_for('login'))
        
        return render_template('register_new.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        """Déconnexion"""
        logout_user()
        flash('Vous avez été déconnecté', 'info')
        return redirect(url_for('login'))
    
    @app.route('/search')
    @login_required
    def search():
        """Page de recherche"""
        query = request.args.get('query', '').lower()
        genre = request.args.get('genre', '').lower()
        anime_data = load_anime_data()
        
        filtered = []
        for anime in anime_data:
            title_match = query in anime.get('title', '').lower() if query else True
            genre_match = not genre or genre in [g.lower() for g in anime.get('genres', [])]
            has_episodes = anime.get('has_episodes', False)
            
            if title_match and genre_match and has_episodes:
                filtered.append(anime)
        
        filtered = filtered[:100]
        recent = [a for a in anime_data if a.get('has_episodes', False)][-20:]
        
        return render_template('search.html',
                              anime_list=filtered,
                              query=query,
                              selected_genre=genre,
                              genres=get_all_genres(),
                              other_anime_list=recent if not filtered else [])
    
    @app.route('/anime/<int:anime_id>')
    @login_required
    def anime_detail(anime_id):
        """Page de détails d'un anime"""
        anime_data = load_anime_data()
        anime = next((a for a in anime_data if int(a.get('anime_id', 0)) == anime_id), None)
        if not anime:
            anime = next((a for a in anime_data if int(a.get('id', 0)) == anime_id), None)
        
        if not anime:
            return render_template('404.html', message="Anime non trouvé"), 404
        
        # Trier les saisons
        if anime.get('seasons'):
            regular, kai, films = [], [], []
            for season in anime['seasons']:
                name = season.get('name', '')
                if season.get('season_number') == 99:
                    films.append(season)
                elif 'Kai' in name:
                    kai.append(season)
                else:
                    regular.append(season)
            
            regular.sort(key=lambda s: s.get('season_number', 0))
            kai.sort(key=lambda s: s.get('season_number', 0))
            anime['seasons'] = regular + films + kai
        
        # Infos utilisateur
        is_favorite = False
        episode_progress = {}
        latest_progress = None
        
        if current_user.is_authenticated:
            try:
                is_favorite = UserFavorite.query.filter_by(
                    user_id=current_user.id,
                    anime_id=anime_id
                ).first() is not None
                
                for progress in UserProgress.query.filter_by(user_id=current_user.id, anime_id=anime_id).all():
                    key = f"{progress.season_number}_{progress.episode_number}"
                    episode_progress[key] = {
                        'time_position': progress.time_position,
                        'completed': progress.completed,
                        'last_watched': progress.last_watched
                    }
                
                latest_progress = UserProgress.query.filter_by(
                    user_id=current_user.id,
                    anime_id=anime_id,
                    completed=False
                ).order_by(UserProgress.last_watched.desc()).first()
            except Exception as e:
                logger.error(f"Erreur: {e}")
        
        return render_template('anime_new.html',
                              anime=anime,
                              is_favorite=is_favorite,
                              episode_progress=episode_progress,
                              latest_progress=latest_progress)
    
    @app.route('/player/<int:anime_id>/<int:season_num>/<int:episode_num>')
    @login_required
    def player(anime_id, season_num, episode_num):
        """Lecteur vidéo"""
        anime_data = load_anime_data()
        anime = next((a for a in anime_data if int(a.get('anime_id', 0)) == anime_id), None)
        if not anime:
            anime = next((a for a in anime_data if int(a.get('id', 0)) == anime_id), None)
        
        if not anime:
            return render_template('404.html', message="Anime non trouvé"), 404
        
        season = next((s for s in anime.get('seasons', []) 
                      if s.get('season_number') == season_num), None)
        if not season:
            return render_template('404.html', message="Saison non trouvée"), 404
        
        episode = next((e for e in season.get('episodes', []) 
                       if e.get('episode_number') == episode_num), None)
        if not episode:
            return render_template('404.html', message="Épisode non trouvé"), 404
        
        # URL vidéo
        video_urls = episode.get('urls', {})
        video_url = ""
        episode_lang = "?"
        
        if 'VF' in video_urls and video_urls['VF']:
            video_url = video_urls['VF'][0] if isinstance(video_urls['VF'], list) else video_urls['VF']
            episode_lang = "VF"
        elif 'VOSTFR' in video_urls and video_urls['VOSTFR']:
            video_url = video_urls['VOSTFR'][0] if isinstance(video_urls['VOSTFR'], list) else video_urls['VOSTFR']
            episode_lang = "VOSTFR"
        
        if not video_url:
            return render_template('404.html', message="Source vidéo non disponible"), 404
        
        download_url = video_url
        if "sendvid.com" in video_url and "/embed/" not in video_url:
            video_id = video_url.split("/")[-1].split(".")[0]
            download_url = f"https://sendvid.com/embed/{video_id}"
        
        # Progression
        time_position = 0
        is_favorite = False
        
        if current_user.is_authenticated:
            try:
                progress = UserProgress.query.filter_by(
                    user_id=current_user.id,
                    anime_id=anime_id,
                    season_number=season_num,
                    episode_number=episode_num
                ).first()
                
                if progress:
                    time_position = progress.time_position
                
                is_favorite = UserFavorite.query.filter_by(
                    user_id=current_user.id,
                    anime_id=anime_id
                ).first() is not None
            except Exception as e:
                logger.error(f"Erreur: {e}")
        
        return render_template('player.html',
                              anime=anime,
                              season=season,
                              episode=episode,
                              download_url=download_url,
                              time_position=time_position,
                              is_favorite=is_favorite,
                              episode_lang=episode_lang)
    
    # ... (Autres routes: profile, settings, categories, etc. - identiques)
    
    # ==================
    # API VIDÉO SEGMENTÉE
    # ==================
    
    @app.route('/api/video/info', methods=['POST'])
    @login_required
    def video_info():
        """Obtenir les infos sur la vidéo (auto-détection du type)"""
        try:
            data = request.get_json()
            url = data.get('url', '').strip()
            
            if not url:
                return jsonify({'success': False, 'error': 'URL manquante'}), 400
            
            player_type, video_id = parse_video_url(url)
            
            if not player_type:
                return jsonify({
                    'success': False,
                    'error': 'Type de lecteur non supporté'
                }), 400
            
            video_key = f"{player_type}_{video_id}"
            
            if player_type == 'vidmoly':
                embed_url = f"https://vidmoly.net/embed-{video_id}.html"
                m3u8_url = extract_vidmoly_m3u8(embed_url)
                
                if not m3u8_url:
                    return jsonify({'success': False, 'error': 'M3U8 non trouvé'}), 404
                
                playlist_url, playlist = get_hls_segments(m3u8_url)
                
                if not playlist or not playlist.segments:
                    return jsonify({'success': False, 'error': 'Segments non trouvés'}), 500
                
                app.config[f'video_{video_key}'] = {
                    'player_type': 'vidmoly',
                    'url': playlist_url,
                    'playlist': playlist
                }
                
                return jsonify({
                    'success': True,
                    'player_type': 'vidmoly',
                    'video_key': video_key,
                    'segments': len(playlist.segments)
                })
            
            elif player_type == 'sibnet':
                embed_url = f"https://video.sibnet.ru/shell.php?videoid={video_id}"
                m3u8_url = extract_sibnet_m3u8(embed_url)
                
                if not m3u8_url:
                    return jsonify({'success': False, 'error': 'M3U8 non trouvé'}), 404
                
                playlist_url, playlist = get_hls_segments(m3u8_url)
                
                if not playlist or not playlist.segments:
                    return jsonify({'success': False, 'error': 'Segments non trouvés'}), 500
                
                app.config[f'video_{video_key}'] = {
                    'player_type': 'sibnet',
                    'url': playlist_url,
                    'playlist': playlist
                }
                
                return jsonify({
                    'success': True,
                    'player_type': 'sibnet',
                    'video_key': video_key,
                    'segments': len(playlist.segments)
                })
            
            elif player_type == 'sendvid':
                embed_url = f"https://sendvid.com/embed/{video_id}"
                video_url = extract_sendvid_video(embed_url)
                
                if not video_url:
                    return jsonify({'success': False, 'error': 'Vidéo non trouvée'}), 404
                
                app.config[f'video_{video_key}'] = {
                    'player_type': 'sendvid',
                    'url': video_url
                }
                
                return jsonify({
                    'success': True,
                    'player_type': 'sendvid',
                    'video_key': video_key
                })
            
        except Exception as e:
            logger.error(f"Erreur API info: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/video/stream/<video_key>')
    @login_required
    def video_stream(video_key):
        """Stream la vidéo (HLS ou MP4 selon le type)"""
        video_data = app.config.get(f'video_{video_key}')
        if not video_data:
            return "Non trouvé", 404
        
        player_type = video_data['player_type']
        
        if player_type in ['vidmoly', 'sibnet']:
            # Génère manifest HLS
            playlist = video_data['playlist']
            base_url = video_data['url'].rsplit('/', 1)[0] + '/'
            
            manifest = "#EXTM3U\n#EXT-X-VERSION:3\n"
            manifest += f"#EXT-X-TARGETDURATION:{int(max(s.duration for s in playlist.segments if s.duration) + 1)}\n"
            manifest += "#EXT-X-MEDIA-SEQUENCE:0\n\n"
            
            for i, seg in enumerate(playlist.segments):
                seg_url = seg.uri if seg.uri.startswith('http') else urljoin(base_url, seg.uri)
                app.config[f'segment_{video_key}_{i}'] = seg_url
                manifest += f"#EXTINF:{seg.duration},\n/api/video/segment/{video_key}/{i}\n"
            
            manifest += "#EXT-X-ENDLIST\n"
            
            return Response(manifest, mimetype='application/vnd.apple.mpegurl')
        
        else:  # sendvid
            video_url = video_data['url']
            range_header = request.headers.get('Range')
            
            headers = video_session.headers.copy()
            if range_header:
                headers['Range'] = range_header
            
            response = video_session.get(video_url, headers=headers, stream=True, timeout=30)
            
            def generate():
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            
            resp_headers = {'Accept-Ranges': 'bytes'}
            if range_header:
                resp_headers['Content-Range'] = response.headers.get('Content-Range', '')
                resp_headers['Content-Length'] = response.headers.get('Content-Length', '')
            
            return Response(generate(), status=response.status_code, mimetype='video/mp4', headers=resp_headers)
    
    @app.route('/api/video/segment/<video_key>/<int:segment_num>')
    @login_required
    def video_segment(video_key, segment_num):
        """Proxy un segment HLS"""
        segment_url = app.config.get(f'segment_{video_key}_{segment_num}')
        if not segment_url:
            return "Non trouvé", 404
        
        response = video_session.get(segment_url, timeout=15, stream=True)
        
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        return Response(generate(), mimetype='video/mp2t')
    
    @app.route('/api/video/download/<video_key>')
    @login_required
    def video_download(video_key):
        """Télécharge la vidéo complète"""
        video_data = app.config.get(f'video_{video_key}')
        if not video_data:
            return "Non trouvé", 404
        
        player_type = video_data['player_type']
        
        if player_type == 'sendvid':
            video_url = video_data['url']
            response = video_session.get(video_url, stream=True, timeout=30)
            
            def generate():
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        yield chunk
            
            return Response(
                generate(),
                mimetype='video/mp4',
                headers={'Content-Disposition': f'attachment; filename="video_{video_key}.mp4"'}
            )
        
        else:  # vidmoly ou sibnet
            playlist = video_data['playlist']
            base_url = video_data['url'].rsplit('/', 1)[0] + '/'
            
            def generate():
                for seg in playlist.segments:
                    seg_url = seg.uri if seg.uri.startswith('http') else urljoin(base_url, seg.uri)
                    try:
                        response = video_session.get(seg_url, timeout=15)
                        if response.status_code == 200:
                            yield response.content
                    except:
                        pass
            
            return Response(
                generate(),
                mimetype='video/mp2t',
                headers={'Content-Disposition': f'attachment; filename="video_{video_key}.ts"'}
            )
    
    # ==================
    # ROUTES UTILISATEUR
    # ==================
    
    @app.route('/profile')
    @login_required
    def profile():
        """Page de profil"""
        anime_data = load_anime_data()
        
        watching_anime = []
        for progress in UserProgress.query.filter_by(user_id=current_user.id).order_by(UserProgress.last_watched.desc()).all():
            anime = next((a for a in anime_data if int(a.get('id', 0)) == progress.anime_id), None)
            if anime:
                season = next((s for s in anime.get('seasons', []) if s.get('season_number') == progress.season_number), None)
                episode = next((e for e in season.get('episodes', []) if e.get('episode_number') == progress.episode_number), None) if season else None
                
                watching_anime.append({
                    'progress': progress,
                    'anime': anime,
                    'season': season,
                    'episode': episode
                })
        
        favorite_anime = []
        for fav in UserFavorite.query.filter_by(user_id=current_user.id).all():
            anime = next((a for a in anime_data if int(a.get('id', 0)) == fav.anime_id), None)
            if anime:
                favorite_anime.append(anime)
        
        return render_template('profile_new.html',
                              watching_anime=watching_anime,
                              favorite_anime=favorite_anime)
    
    @app.route('/settings', methods=['GET', 'POST'])
    @login_required
    def settings():
        """Page de paramètres"""
        if request.method == 'POST':
            current_password = request.form.get('current_password')
            new_username = request.form.get('new_username')
            new_password = request.form.get('new_password')
            confirm = request.form.get('confirm_password')
            
            if not current_user.check_password(current_password):
                flash('Mot de passe actuel incorrect', 'danger')
                return redirect(url_for('settings'))
            
            if new_username and new_username != current_user.username:
                if User.query.filter_by(username=new_username).first():
                    flash('Nom d\'utilisateur déjà pris', 'danger')
                    return redirect(url_for('settings'))
                current_user.username = new_username
            
            if new_password:
                if new_password != confirm:
                    flash('Les nouveaux mots de passe ne correspondent pas', 'danger')
                    return redirect(url_for('settings'))
                current_user.set_password(new_password)
            
            db.session.commit()
            flash('Paramètres mis à jour', 'success')
            return redirect(url_for('settings'))
        
        return render_template('settings.html')
    
    @app.route('/save-progress', methods=['POST'])
    @login_required
    def save_progress():
        """Sauvegarde la progression"""
        anime_id = request.form.get('anime_id', type=int)
        season_number = request.form.get('season_number', type=int)
        episode_number = request.form.get('episode_number', type=int)
        time_position = request.form.get('time_position', type=float)
        completed = request.form.get('completed') == 'true'
        
        progress = UserProgress.query.filter_by(
            user_id=current_user.id,
            anime_id=anime_id,
            season_number=season_number,
            episode_number=episode_number
        ).first()
        
        if progress:
            if not progress.completed or time_position < progress.time_position * 0.5:
                progress.time_position = time_position
                progress.completed = completed
            progress.last_watched = datetime.datetime.now(datetime.timezone.utc)
        else:
            progress = UserProgress(
                user_id=current_user.id,
                anime_id=anime_id,
                season_number=season_number,
                episode_number=episode_number,
                time_position=time_position,
                completed=completed
            )
            db.session.add(progress)
        
        db.session.commit()
        return jsonify({'success': True})
    
    @app.route('/toggle-favorite', methods=['POST'])
    @login_required
    def toggle_favorite():
        """Toggle favori"""
        anime_id = request.form.get('anime_id', type=int)
        favorite = UserFavorite.query.filter_by(user_id=current_user.id, anime_id=anime_id).first()
        
        if favorite:
            db.session.delete(favorite)
            db.session.commit()
            return jsonify({'success': True, 'action': 'removed'})
        else:
            favorite = UserFavorite(user_id=current_user.id, anime_id=anime_id)
            db.session.add(favorite)
            db.session.commit()
            return jsonify({'success': True, 'action': 'added'})
    
    @app.route('/remove-from-watching', methods=['POST'])
    @login_required
    def remove_from_watching():
        """Retire de la liste de visionnage"""
        anime_id = request.form.get('anime_id', type=int)
        if anime_id:
            UserProgress.query.filter_by(user_id=current_user.id, anime_id=anime_id).delete()
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'ID manquant'})
    
    @app.route('/categories')
    @login_required
    def categories():
        """Page des catégories"""
        anime_data = load_anime_data()
        genres = get_all_genres()
        
        genres_dict = {genre: [] for genre in genres}
        for anime in anime_data:
            for genre in anime.get('genres', []):
                if genre.lower() in genres_dict:
                    genres_dict[genre.lower()].append(anime)
        
        return render_template('categories.html',
                              all_anime=anime_data,
                              genres=genres,
                              genres_dict=genres_dict)
    
    @app.route('/documentation')
    @login_required
    def documentation():
        """Page de documentation"""
        return render_template('documentation.html')
    
    @app.errorhandler(404)
    def page_not_found(e):
        """Erreur 404"""
        template = '404.html' if current_user.is_authenticated else '404_public.html'
        return render_template(template), 404
    
    @app.errorhandler(500)
    def server_error(e):
        """Erreur 500"""
        logger.error(f"Erreur serveur: {e}")
        template = '404.html' if current_user.is_authenticated else '404_public.html'
        return render_template(template), 500
    
    logger.info(f"✅ {len(app.url_map._rules)} routes enregistrées")
    
    return app


# ==================
# POINT D'ENTRÉE
# ==================

if __name__ == '__main__':
    app = create_app()
    
    print("\n" + "="*60)
    print("🚀 AnimeZone - Mode Dataset Local avec Segmentation Vidéo")
    print("📍 http://localhost:8080")
    print(f"📊 {len(app.url_map._rules)} routes disponibles")
    print("🎬 Support: Vidmoly, Sibnet, SendVid")
    print("="*60 + "\n")
    
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
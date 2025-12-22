"""
app.py - Backend API optimisé pour AnimeZone
Performance : Cache + Queries optimisées
"""

import os
import json
import logging
import datetime
from functools import lru_cache
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import requests

# ==================
# CONFIGURATION
# ==================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = SQLAlchemy()
login_manager = LoginManager()

# Session vidéo réutilisable
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
video_session = requests.Session()
video_session.headers.update({'User-Agent': USER_AGENT})

# ==================
# MODÈLES DB (avec indexes)
# ==================

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class UserProgress(db.Model):
    __tablename__ = 'user_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    anime_id = db.Column(db.Integer, nullable=False, index=True)
    season_number = db.Column(db.Integer, nullable=False)
    episode_number = db.Column(db.Integer, nullable=False)
    time_position = db.Column(db.Float, default=0)
    completed = db.Column(db.Boolean, default=False)
    last_watched = db.Column(db.DateTime, default=datetime.datetime.utcnow, index=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'anime_id', 'season_number', 'episode_number'),
        db.Index('idx_user_anime', 'user_id', 'anime_id'),
    )


class UserFavorite(db.Model):
    __tablename__ = 'user_favorite'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    anime_id = db.Column(db.Integer, nullable=False, index=True)
    added_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'anime_id'),
    )


# ==================
# 🔥 CACHE OPTIMISÉ
# ==================

# Cache le JSON en mémoire (rechargé seulement au redémarrage)
_ANIME_CACHE = None
_ANIME_DICT = None  # Dict pour recherche O(1)

def load_anime_data():
    """Cache le JSON en mémoire - appelé UNE SEULE FOIS"""
    global _ANIME_CACHE, _ANIME_DICT
    
    if _ANIME_CACHE is not None:
        return _ANIME_CACHE
    
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, 'static', 'data', 'anime.json')
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            animes = data.get('anime', data) if isinstance(data, dict) else data
            
            # Normaliser les données
            for anime in animes:
                if 'anime_id' not in anime:
                    anime['anime_id'] = anime.get('id', 0)
                if 'has_episodes' not in anime:
                    anime['has_episodes'] = len(anime.get('seasons', [])) > 0
            
            _ANIME_CACHE = animes
            
            # Créer dict pour recherche rapide
            _ANIME_DICT = {int(a.get('anime_id', 0)): a for a in animes}
            _ANIME_DICT.update({int(a.get('id', 0)): a for a in animes})
            
            logger.info(f"✅ Cache chargé : {len(animes)} animes")
            return animes
    except Exception as e:
        logger.error(f"❌ Erreur chargement cache: {e}")
        return []


def get_anime_by_id(anime_id):
    """Recherche O(1) au lieu de O(n)"""
    if _ANIME_DICT is None:
        load_anime_data()
    return _ANIME_DICT.get(int(anime_id))


@lru_cache(maxsize=1)
def load_discover_data():
    """Cache les données discover"""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, 'data_discover.json')
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else data.get('anime', [])
    except:
        return []


@lru_cache(maxsize=1)
def get_all_genres():
    """Cache les genres"""
    anime_data = load_anime_data()
    genres = set()
    for anime in anime_data:
        for genre in anime.get('genres', []):
            genres.add(genre.lower())
    return sorted(list(genres))


# ==================
# 🔥 QUERIES OPTIMISÉES
# ==================

def get_user_progress_optimized(user_id, limit=20):
    """Query optimisée avec limite"""
    return (UserProgress.query
            .filter_by(user_id=user_id)
            .order_by(UserProgress.last_watched.desc())
            .limit(limit)
            .all())


def get_user_favorites_optimized(user_id, limit=15):
    """Query optimisée avec limite"""
    return (UserFavorite.query
            .filter_by(user_id=user_id)
            .order_by(UserFavorite.added_at.desc())
            .limit(limit)
            .all())


def get_episode_progress_batch(user_id, anime_id):
    """Récupère TOUTE la progression d'un anime en 1 query"""
    progress_list = UserProgress.query.filter_by(
        user_id=user_id,
        anime_id=anime_id
    ).all()
    
    return {
        f"{p.season_number}_{p.episode_number}": {
            'time_position': p.time_position,
            'completed': p.completed,
            'last_watched': p.last_watched
        }
        for p in progress_list
    }


# ==================
# API ENDPOINTS
# ==================

def register_api_routes(app):
    """Enregistre toutes les routes API"""
    
    @app.route('/api/auth/login', methods=['POST'])
    def api_login():
        """API Login - retourne JSON"""
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            user.last_login = datetime.datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True, 'user_id': user.id})
        
        return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
    
    
    @app.route('/api/auth/register', methods=['POST'])
    def api_register():
        """API Register"""
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'error': 'Username taken'}), 400
        
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'success': True, 'user_id': user.id})
    
    
    @app.route('/api/anime/list')
    @login_required
    def api_anime_list():
        """Liste des animes (depuis cache)"""
        anime_data = load_anime_data()
        
        # Filtres
        query = request.args.get('query', '').lower()
        genre = request.args.get('genre', '').lower()
        limit = int(request.args.get('limit', 100))
        
        filtered = anime_data
        
        if query:
            filtered = [a for a in filtered if query in a.get('title', '').lower()]
        
        if genre:
            filtered = [a for a in filtered if genre in [g.lower() for g in a.get('genres', [])]]
        
        # Limiter les résultats
        filtered = filtered[:limit]
        
        return jsonify({'success': True, 'animes': filtered, 'total': len(filtered)})
    
    
    @app.route('/api/anime/<int:anime_id>')
    @login_required
    def api_anime_detail(anime_id):
        """Détails d'un anime (recherche O(1))"""
        anime = get_anime_by_id(anime_id)
        
        if not anime:
            return jsonify({'success': False, 'error': 'Not found'}), 404
        
        # Progression de l'utilisateur (1 seule query)
        episode_progress = get_episode_progress_batch(current_user.id, anime_id)
        
        # Favori (1 query)
        is_favorite = UserFavorite.query.filter_by(
            user_id=current_user.id,
            anime_id=anime_id
        ).first() is not None
        
        return jsonify({
            'success': True,
            'anime': anime,
            'is_favorite': is_favorite,
            'episode_progress': episode_progress
        })
    
    
    @app.route('/api/user/progress')
    @login_required
    def api_user_progress():
        """Progression utilisateur optimisée"""
        limit = int(request.args.get('limit', 20))
        progress_list = get_user_progress_optimized(current_user.id, limit)
        
        # Enrichir avec les données anime (depuis cache)
        result = []
        for progress in progress_list:
            anime = get_anime_by_id(progress.anime_id)
            if anime:
                result.append({
                    'progress': {
                        'anime_id': progress.anime_id,
                        'season_number': progress.season_number,
                        'episode_number': progress.episode_number,
                        'time_position': progress.time_position,
                        'completed': progress.completed,
                        'last_watched': progress.last_watched.isoformat()
                    },
                    'anime': anime
                })
        
        return jsonify({'success': True, 'progress': result})
    
    
    @app.route('/api/user/favorites')
    @login_required
    def api_user_favorites():
        """Favoris utilisateur optimisés"""
        limit = int(request.args.get('limit', 15))
        favorites = get_user_favorites_optimized(current_user.id, limit)
        
        result = []
        for fav in favorites:
            anime = get_anime_by_id(fav.anime_id)
            if anime:
                result.append(anime)
        
        return jsonify({'success': True, 'favorites': result})
    
    
    @app.route('/api/progress/save', methods=['POST'])
    @login_required
    def api_save_progress():
        """Sauvegarde optimisée avec upsert"""
        data = request.get_json()
        
        anime_id = data.get('anime_id', type=int)
        season_number = data.get('season_number', type=int)
        episode_number = data.get('episode_number', type=int)
        time_position = data.get('time_position', type=float)
        completed = data.get('completed', False)
        
        # Upsert en 1 query
        progress = UserProgress.query.filter_by(
            user_id=current_user.id,
            anime_id=anime_id,
            season_number=season_number,
            episode_number=episode_number
        ).first()
        
        if progress:
            progress.time_position = time_position
            progress.completed = completed
            progress.last_watched = datetime.datetime.utcnow()
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
    
    
    @app.route('/api/favorite/toggle', methods=['POST'])
    @login_required
    def api_toggle_favorite():
        """Toggle favori optimisé"""
        data = request.get_json()
        anime_id = data.get('anime_id', type=int)
        
        favorite = UserFavorite.query.filter_by(
            user_id=current_user.id,
            anime_id=anime_id
        ).first()
        
        if favorite:
            db.session.delete(favorite)
            action = 'removed'
        else:
            favorite = UserFavorite(user_id=current_user.id, anime_id=anime_id)
            db.session.add(favorite)
            action = 'added'
        
        db.session.commit()
        return jsonify({'success': True, 'action': action})


# ==================
# FACTORY
# ==================

def create_app():
    """Factory optimisée"""
    app = Flask(__name__)
    
    # Config
    app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key_123")
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///anime.db"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,
        'pool_recycle': 3600,
    }
    
    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))
    
    # Créer tables + indexes
    with app.app_context():
        db.create_all()
        logger.info("✅ DB initialisée avec indexes")
        
        # Précharger le cache au démarrage
        load_anime_data()
        load_discover_data()
        get_all_genres()
        logger.info("✅ Cache préchargé")
    
    # Enregistrer les routes API
    register_api_routes(app)
    
    return app


if __name__ == '__main__':
    app = create_app()
    logger.info("🚀 Backend API ready")
    app.run(host='0.0.0.0', port=8080, debug=True)
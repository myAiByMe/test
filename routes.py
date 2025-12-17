"""
Routes pour AnimeZone
Fonction register_routes pour enregistrer toutes les routes sur l'app
"""

import os
import json
import logging
import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_user, login_required, logout_user, current_user

from app import db

logger = logging.getLogger(__name__)

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
# FONCTION D'ENREGISTREMENT DES ROUTES
# ==================

def register_routes(app):
    """Enregistre toutes les routes sur l'application Flask"""
    
    # Récupérer les modèles depuis app
    User = app.User
    UserProgress = app.UserProgress
    UserFavorite = app.UserFavorite
    
    # Importer db depuis le module app pour avoir accès à la session
    from app import db as database
    
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
                user.last_login = datetime.datetime.utcnow()
                database.session.commit()
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
                database.session.add(user)
                database.session.commit()
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
            
            database.session.commit()
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
            database.session.add(progress)
        
        database.session.commit()
        return jsonify({'success': True})
    
    @app.route('/toggle-favorite', methods=['POST'])
    @login_required
    def toggle_favorite():
        """Toggle favori"""
        anime_id = request.form.get('anime_id', type=int)
        favorite = UserFavorite.query.filter_by(user_id=current_user.id, anime_id=anime_id).first()
        
        if favorite:
            database.session.delete(favorite)
            database.session.commit()
            return jsonify({'success': True, 'action': 'removed'})
        else:
            favorite = UserFavorite(user_id=current_user.id, anime_id=anime_id)
            database.session.add(favorite)
            database.session.commit()
            return jsonify({'success': True, 'action': 'added'})
    
    @app.route('/remove-from-watching', methods=['POST'])
    @login_required
    def remove_from_watching():
        """Retire de la liste de visionnage"""
        anime_id = request.form.get('anime_id', type=int)
        if anime_id:
            UserProgress.query.filter_by(user_id=current_user.id, anime_id=anime_id).delete()
            database.session.commit()
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
"""
routes.py - Frontend (templates + logique utilisateur)
À importer dans app.py
"""

import re
import logging
import m3u8
import requests
from urllib.parse import urljoin
from flask import render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_user, login_required, logout_user, current_user

from app import (
    db, User, UserProgress, UserFavorite,
    load_anime_data, get_anime_by_id, load_discover_data,
    get_all_genres, get_user_progress_optimized,
    get_user_favorites_optimized, video_session
)

logger = logging.getLogger(__name__)

# ==================
# SYSTÈME VIDÉO (inchangé mais optimisé)
# ==================

def parse_video_url(url):
    """Parse URL vidéo"""
    if not url:
        return None, None
    
    url_clean = url.strip().lower()
    
    # SENDVID
    if 'sendvid' in url_clean:
        match = re.search(r'sendvid\.com/embed/([a-zA-Z0-9]+)', url, re.IGNORECASE)
        if match:
            return ('sendvid', match.group(1))
        
        match = re.search(r'sendvid\.com/([a-zA-Z0-9]+)', url, re.IGNORECASE)
        if match:
            return ('sendvid', match.group(1))
    
    # VIDMOLY
    if 'vidmoly' in url_clean:
        match = re.search(r'embed-([a-zA-Z0-9]+)\.html', url, re.IGNORECASE)
        if match:
            return ('vidmoly', match.group(1))
    
    return None, None


def extract_vidmoly_m3u8(embed_url):
    """Extrait M3U8 Vidmoly"""
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
    except Exception as e:
        logger.error(f"Erreur Vidmoly M3U8: {e}")
        return None


def extract_sendvid_video(embed_url):
    """Extrait URL MP4 SendVid"""
    try:
        response = video_session.get(embed_url, timeout=10)
        html = response.text
        
        # Pattern 1: <source>
        pattern1 = r'<source[^>]*src=["\']([^"\']+\.mp4[^"\']*)["\']'
        match = re.search(pattern1, html, re.IGNORECASE)
        if match:
            url = match.group(1)
            return url if url.startswith('http') else urljoin('https://sendvid.com', url)
        
        # Pattern 2: file variable
        pattern2 = r'file\s*:\s*["\']([^"\']+\.(mp4|webm)[^"\']*)["\']'
        match = re.search(pattern2, html, re.IGNORECASE)
        if match:
            url = match.group(1)
            return url if url.startswith('http') else urljoin('https://sendvid.com', url)
        
        return None
    except Exception as e:
        logger.error(f"Erreur SendVid: {e}")
        return None


def get_hls_segments(master_url):
    """Récupère segments HLS"""
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
    except Exception as e:
        logger.error(f"Erreur HLS: {e}")
        return None, None


# ==================
# ROUTES FRONTEND
# ==================

def register_frontend_routes(app):
    """Enregistre toutes les routes frontend"""
    
    @app.route('/')
    def index():
        """Page d'accueil OPTIMISÉE"""
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        
        # 🔥 Utilise le cache
        anime_data = load_anime_data()
        
        # Continue watching (query optimisée)
        continue_watching = []
        latest_progress = get_user_progress_optimized(current_user.id, limit=20)
        
        processed = set()
        for progress in latest_progress:
            if progress.anime_id not in processed:
                anime = get_anime_by_id(progress.anime_id)  # 🔥 O(1)
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
        
        # Favoris (query optimisée)
        favorite_anime = []
        favorites = get_user_favorites_optimized(current_user.id, limit=15)
        for fav in favorites:
            anime = get_anime_by_id(fav.anime_id)  # 🔥 O(1)
            if anime:
                favorite_anime.append(anime)
        
        # Featured (depuis cache)
        featured = load_discover_data()
        featured = [a for a in featured if a.get('has_episodes', False)][:12]
        
        return render_template('index_new.html',
                              anime_list=featured,
                              continue_watching=continue_watching,
                              favorite_anime=favorite_anime)
    
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Login OPTIMISÉ"""
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            # 🔥 Query avec index
            user = User.query.filter_by(username=username).first()
            
            if user and user.check_password(password):
                import datetime
                user.last_login = datetime.datetime.utcnow()
                db.session.commit()
                login_user(user)
                
                next_page = request.args.get('next')
                return redirect(next_page if next_page else url_for('index'))
            
            flash('Nom d\'utilisateur ou mot de passe incorrect', 'danger')
        
        return render_template('login_new.html')
    
    
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        """Register"""
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
        """Recherche OPTIMISÉE"""
        query = request.args.get('query', '').lower()
        genre = request.args.get('genre', '').lower()
        
        # 🔥 Depuis cache
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
        """Détails anime OPTIMISÉ"""
        # 🔥 Recherche O(1)
        anime = get_anime_by_id(anime_id)
        
        if not anime:
            return render_template('404.html', message="Anime non trouvé"), 404
        
        # Trier saisons
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
        
        # Infos utilisateur (queries optimisées)
        is_favorite = UserFavorite.query.filter_by(
            user_id=current_user.id,
            anime_id=anime_id
        ).first() is not None
        
        # 🔥 1 seule query pour TOUTE la progression
        episode_progress = {}
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
        
        return render_template('anime_new.html',
                              anime=anime,
                              is_favorite=is_favorite,
                              episode_progress=episode_progress,
                              latest_progress=latest_progress)
    
    
    @app.route('/player/<int:anime_id>/<int:season_num>/<int:episode_num>')
    @login_required
    def player(anime_id, season_num, episode_num):
        """Lecteur OPTIMISÉ"""
        # 🔥 O(1)
        anime = get_anime_by_id(anime_id)
        
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
        
        # Sélection URL
        def select_best_url(urls_dict):
            if not urls_dict:
                return None, None
            
            def prioritize(url_list):
                if not url_list:
                    return None
                if isinstance(url_list, str):
                    url_list = [url_list]
                
                vidmoly = [u for u in url_list if 'vidmoly' in u.lower()]
                sendvid = [u for u in url_list if 'sendvid' in u.lower()]
                
                return (vidmoly or sendvid or url_list)[0] if (vidmoly or sendvid or url_list) else None
            
            for lang in ['VF', 'VOSTFR']:
                if lang in urls_dict:
                    url = prioritize(urls_dict[lang])
                    if url:
                        return url, lang
            
            for lang, urls in urls_dict.items():
                url = prioritize(urls)
                if url:
                    return url, lang
            
            return None, None
        
        video_url, episode_lang = select_best_url(episode.get('urls', {}))
        
        if not video_url:
            return render_template('404.html', message="Source vidéo non disponible"), 404
        
        download_url = video_url
        if "sendvid.com" in video_url and "/embed/" not in video_url:
            video_id = video_url.split("/")[-1].split(".")[0]
            download_url = f"https://sendvid.com/embed/{video_id}"
        
        # Progression (1 query)
        time_position = 0
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
        """Profil OPTIMISÉ"""
        anime_data = load_anime_data()
        
        # 🔥 Query limitée
        watching_anime = []
        for progress in get_user_progress_optimized(current_user.id, limit=50):
            anime = get_anime_by_id(progress.anime_id)  # O(1)
            if anime:
                season = next((s for s in anime.get('seasons', []) 
                             if s.get('season_number') == progress.season_number), None)
                episode = next((e for e in season.get('episodes', []) 
                              if e.get('episode_number') == progress.episode_number), None) if season else None
                
                watching_anime.append({
                    'progress': progress,
                    'anime': anime,
                    'season': season,
                    'episode': episode
                })
        
        # Favoris optimisés
        favorite_anime = []
        for fav in get_user_favorites_optimized(current_user.id, limit=50):
            anime = get_anime_by_id(fav.anime_id)  # O(1)
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

    @app.route('/categories')
    @login_required
    def categories():
        """Catégories (depuis cache)"""
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
    
    
    # ==================
    # API VIDÉO (inchangé)
    # ==================
    
    @app.route('/api/video/info', methods=['POST'])
    @login_required
    def video_info():
        """Info vidéo"""
        try:
            data = request.get_json()
            url = data.get('url', '').strip()
            
            if not url:
                return jsonify({'success': False, 'error': 'URL manquante'}), 400
            
            player_type, video_id = parse_video_url(url)
            
            if not player_type:
                return jsonify({'success': False, 'error': 'Type non supporté', 'use_iframe': True}), 400
            
            video_key = f"{player_type}_{video_id}"
            
            # VIDMOLY
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
            
            # SENDVID
            elif player_type == 'sendvid':
                embed_url = f"https://sendvid.com/embed/{video_id}"
                video_url = extract_sendvid_video(embed_url)
                
                if not video_url:
                    return jsonify({'success': False, 'error': 'Vidéo non trouvée'}), 404
                
                try:
                    head_response = video_session.head(video_url, timeout=10, allow_redirects=True)
                    accepts_range = 'bytes' in head_response.headers.get('Accept-Ranges', '').lower()
                    total_size = int(head_response.headers.get('Content-Length', 0))
                except:
                    accepts_range = False
                    total_size = 0
                
                app.config[f'video_{video_key}'] = {
                    'player_type': 'sendvid',
                    'url': head_response.url if 'head_response' in locals() else video_url,
                    'accepts_range': accepts_range,
                    'total_size': total_size
                }
                
                return jsonify({
                    'success': True,
                    'player_type': 'sendvid',
                    'video_key': video_key,
                    'direct_mp4': True
                })
            
        except Exception as e:
            logger.error(f"Erreur API info: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    
    @app.route('/api/video/stream/<video_key>')
    @login_required
    def video_stream(video_key):
        """Stream vidéo"""
        video_data = app.config.get(f'video_{video_key}')
        if not video_data:
            return "Non trouvé", 404
        
        player_type = video_data['player_type']
        
        # VIDMOLY (HLS)
        if player_type == 'vidmoly':
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
        
        # SENDVID (MP4 Direct)
        elif player_type == 'sendvid':
            video_url = video_data['url']
            range_header = request.headers.get('Range')
            
            if range_header and video_data.get('accepts_range'):
                headers = video_session.headers.copy()
                headers['Range'] = range_header
                response = video_session.get(video_url, headers=headers, stream=True, timeout=30)
                
                def generate():
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                
                return Response(
                    generate(),
                    status=response.status_code,
                    mimetype='video/mp4',
                    headers={
                        'Content-Range': response.headers.get('Content-Range', ''),
                        'Content-Length': response.headers.get('Content-Length', ''),
                        'Accept-Ranges': 'bytes'
                    }
                )
            else:
                response = video_session.get(video_url, stream=True, timeout=30)
                
                def generate():
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                
                return Response(
                    generate(),
                    mimetype='video/mp4',
                    headers={
                        'Content-Length': str(video_data.get('total_size', 0)),
                        'Accept-Ranges': 'bytes'
                    }
                )
        
        return "Type non supporté", 400
    
    
    @app.route('/api/video/segment/<video_key>/<int:segment_num>')
    @login_required
    def video_segment(video_key, segment_num):
        """Proxy segment Vidmoly"""
        video_data = app.config.get(f'video_{video_key}')
        if not video_data or video_data['player_type'] != 'vidmoly':
            return "Non trouvé", 404
        
        segment_url = app.config.get(f'segment_{video_key}_{segment_num}')
        if not segment_url:
            return "Segment non trouvé", 404
        
        try:
            response = video_session.get(segment_url, timeout=20, stream=True)
            
            def generate():
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            
            return Response(generate(), mimetype='video/mp2t')
        except Exception as e:
            logger.error(f"Erreur segment {segment_num}: {e}")
            return f"Erreur: {str(e)}", 500
    
    
    # ==================
    # ROUTES SIMPLES
    # ==================
    
    @app.route('/save-progress', methods=['POST'])
    @login_required
    def save_progress():
        """Sauvegarde progression"""
        import datetime
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
    
    
    # 🔥 ROUTE MANQUANTE - AJOUTÉE ICI
    @app.route('/remove-from-watching', methods=['POST'])
    @login_required
    def remove_from_watching():
        """Retire un anime de la liste de visionnage"""
        anime_id = request.form.get('anime_id', type=int)
        
        if not anime_id:
            return jsonify({'success': False, 'error': 'ID manquant'}), 400
        
        try:
            # Supprimer toutes les progressions de cet anime pour l'utilisateur
            deleted_count = UserProgress.query.filter_by(
                user_id=current_user.id,
                anime_id=anime_id
            ).delete()
            
            db.session.commit()
            
            logger.info(f"✅ Supprimé {deleted_count} progressions pour anime {anime_id}")
            return jsonify({'success': True, 'deleted': deleted_count})
        
        except Exception as e:
            logger.error(f"❌ Erreur suppression progression: {e}")
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500
    
    
    # ==================
    # ERROR HANDLERS
    # ==================
    
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Erreur 500: {e}")
        return render_template('404.html'), 500
"""
🎬 Serveur Proxy Universel - Vidmoly + SendVid
✅ Détection automatique du type de lecteur
✅ Support HLS (Vidmoly) et MP4 (SendVid)
✅ Téléchargement en MP4 (conversion HLS → MP4)
✅ Sauvegarde automatique de progression
✅ Compatible Render.com

⚠️ USAGE PRIVÉ UNIQUEMENT - PROJET PORTFOLIO
"""

from flask import Flask, Response, render_template_string, jsonify, request
from flask_cors import CORS
import requests
import re
import m3u8
import json
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

app = Flask(__name__)
CORS(app)

# Fichier de progression unique
PROGRESS_FILE = Path('video_progress.json')

# Configuration
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Session persistante
session = requests.Session()
session.headers.update({
    'User-Agent': USER_AGENT,
    'Accept': '*/*',
    'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7'
})

print("="*60)
print("🎬 SERVEUR PROXY UNIVERSEL - VIDMOLY + SENDVID")
print("="*60)
print(f"💾 Progression: {PROGRESS_FILE}")
print("🎯 Support: Vidmoly (HLS) + SendVid (MP4)")
print("📹 Téléchargement: Conversion HLS → MP4")
print("="*60)

# Vérifier si ffmpeg est disponible
def check_ffmpeg():
    """Vérifie si ffmpeg est installé"""
    try:
        subprocess.run(['ffmpeg', '-version'], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL, 
                      check=True)
        print("✅ FFmpeg détecté")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  FFmpeg non trouvé - Téléchargements HLS en .ts seulement")
        return False

FFMPEG_AVAILABLE = check_ffmpeg()

# ============================================
# DÉTECTION DU TYPE DE LECTEUR
# ============================================

def detect_player_type(url):
    """
    Détecte automatiquement le type de lecteur depuis l'URL
    """
    url_lower = url.lower()
    
    if 'vidmoly' in url_lower:
        return 'vidmoly'
    elif 'sendvid' in url_lower:
        return 'sendvid'
    else:
        return None

def parse_video_url(url):
    """
    Parse l'URL et extrait le video_id et le type
    Formats supportés:
    - https://vidmoly.net/embed-XXXXX.html
    - https://sendvid.com/embed/XXXXX
    """
    player_type = detect_player_type(url)
    
    if player_type == 'vidmoly':
        # Format: embed-y2dfh1ndem54.html
        match = re.search(r'embed-([a-zA-Z0-9]+)\.html', url)
        if match:
            return player_type, match.group(1)
    
    elif player_type == 'sendvid':
        # Format: embed/e47tdkrv
        match = re.search(r'embed/([a-zA-Z0-9]+)', url)
        if match:
            return player_type, match.group(1)
    
    return None, None

# ============================================
# GESTION DE LA PROGRESSION
# ============================================

def load_progress():
    """Charge la progression depuis le fichier JSON"""
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_progress(video_key, data):
    """Sauvegarde la progression dans le fichier JSON"""
    try:
        progress = load_progress()
        progress[video_key] = {
            'current_time': data.get('current_time', 0),
            'duration': data.get('duration', 0),
            'timestamp': data.get('timestamp', ''),
            'player_type': data.get('player_type', '')
        }
        
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Progression sauvegardée: {video_key} @ {data.get('current_time')}s")
        return True
    except Exception as e:
        print(f"❌ Erreur sauvegarde: {e}")
        return False

def get_progress(video_key):
    """Récupère la progression pour une vidéo"""
    progress = load_progress()
    return progress.get(video_key, None)

# ============================================
# EXTRACTEURS VIDMOLY
# ============================================

def extract_vidmoly_m3u8(embed_url):
    """Extrait l'URL M3U8 depuis Vidmoly"""
    try:
        print(f"\n🔍 [VIDMOLY] Extraction depuis: {embed_url}")
        
        response = session.get(embed_url, timeout=10)
        response.raise_for_status()
        
        html = response.text
        
        # Pattern pour sources: [{file: "url.m3u8"}]
        pattern = r'sources\s*:\s*\[\s*{\s*file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']'
        match = re.search(pattern, html, re.IGNORECASE)
        
        if match:
            m3u8_url = match.group(1)
            print(f"✅ M3U8 trouvé: {m3u8_url}")
            return m3u8_url
        
        # Pattern alternatif
        pattern2 = r'file\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']'
        match = re.search(pattern2, html, re.IGNORECASE)
        
        if match:
            m3u8_url = match.group(1)
            print(f"✅ M3U8 trouvé: {m3u8_url}")
            return m3u8_url
        
        print("❌ M3U8 non trouvé")
        return None
        
    except Exception as e:
        print(f"❌ Erreur extraction Vidmoly: {e}")
        return None

def get_vidmoly_segment_playlist(master_url):
    """Résout le master playlist pour obtenir le vrai manifeste avec segments"""
    try:
        print(f"📥 [VIDMOLY] Analyse master playlist...")
        
        response = session.get(master_url, timeout=10)
        response.raise_for_status()
        
        master = m3u8.loads(response.text)
        
        if master.segments:
            print(f"✅ Manifeste direct: {len(master.segments)} segments")
            return master_url, master
        
        if master.playlists:
            best_playlist = master.playlists[-1]
            base_url = master_url.rsplit('/', 1)[0] + '/'
            playlist_url = urljoin(base_url, best_playlist.uri)
            
            print(f"🎯 Playlist sélectionnée: {playlist_url}")
            
            response = session.get(playlist_url, timeout=10)
            response.raise_for_status()
            
            playlist = m3u8.loads(response.text)
            
            print(f"✅ {len(playlist.segments)} segments trouvés")
            
            return playlist_url, playlist
        
        return None, None
        
    except Exception as e:
        print(f"❌ Erreur résolution playlist: {e}")
        return None, None

# ============================================
# EXTRACTEURS SENDVID
# ============================================

def extract_sendvid_video(embed_url):
    """Extrait l'URL vidéo directe depuis SendVid"""
    try:
        print(f"\n🔍 [SENDVID] Extraction depuis: {embed_url}")
        
        response = session.get(embed_url, timeout=10)
        response.raise_for_status()
        
        html = response.text
        
        # Pattern 1: balise source
        pattern1 = r'<source[^>]*src=["\']([^"\']+\.mp4[^"\']*)["\']'
        match = re.search(pattern1, html, re.IGNORECASE)
        
        if match:
            video_url = match.group(1)
            if not video_url.startswith('http'):
                video_url = urljoin('https://sendvid.com', video_url)
            print(f"✅ Vidéo trouvée: {video_url}")
            return video_url
        
        # Pattern 2: variable JS
        pattern2 = r'file\s*:\s*["\']([^"\']+\.(mp4|webm)[^"\']*)["\']'
        match = re.search(pattern2, html, re.IGNORECASE)
        
        if match:
            video_url = match.group(1)
            if not video_url.startswith('http'):
                video_url = urljoin('https://sendvid.com', video_url)
            print(f"✅ Vidéo trouvée: {video_url}")
            return video_url
        
        # Pattern 3: URL complète
        pattern3 = r'(https?://[^\s"\'<>]+\.(mp4|webm)[^\s"\'<>]*)'
        match = re.search(pattern3, html)
        
        if match:
            video_url = match.group(1)
            print(f"✅ Vidéo trouvée: {video_url}")
            return video_url
        
        print("❌ Vidéo non trouvée")
        return None
        
    except Exception as e:
        print(f"❌ Erreur extraction SendVid: {e}")
        return None

def get_sendvid_info(video_url):
    """Récupère les infos de la vidéo SendVid"""
    try:
        response = session.head(video_url, timeout=10, allow_redirects=True)
        
        return {
            'url': response.url,
            'size': int(response.headers.get('Content-Length', 0)),
            'type': response.headers.get('Content-Type', 'video/mp4'),
            'accepts_range': 'bytes' in response.headers.get('Accept-Ranges', '').lower()
        }
    except:
        return {
            'url': video_url,
            'size': 0,
            'type': 'video/mp4',
            'accepts_range': False
        }

# ============================================
# ROUTES API
# ============================================

@app.route('/')
def home():
    """Page d'accueil avec lecteur universel"""
    html = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Universal Video Proxy</title>
        <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 1000px;
                width: 100%;
                overflow: hidden;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }
            .header h1 { font-size: 28px; margin-bottom: 8px; }
            .header p { opacity: 0.9; font-size: 14px; }
            .content { padding: 30px; }
            .input-section {
                margin-bottom: 20px;
            }
            .url-input {
                width: 100%;
                padding: 14px 18px;
                border: 2px solid #e5e7eb;
                border-radius: 12px;
                font-size: 15px;
                outline: none;
                transition: all 0.2s ease;
            }
            .url-input:focus {
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }
            .video-container {
                background: #000;
                border-radius: 8px;
                overflow: hidden;
                margin-bottom: 20px;
                aspect-ratio: 16/9;
            }
            video { width: 100%; height: 100%; display: block; }
            .controls {
                display: flex;
                gap: 10px;
                margin-top: 20px;
            }
            button {
                flex: 1;
                padding: 14px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }
            button:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
            .status {
                padding: 16px;
                background: #f3f4f6;
                border-radius: 8px;
                font-size: 14px;
                color: #374151;
                margin-top: 20px;
                font-family: 'Courier New', monospace;
            }
            .status.loading { background: #dbeafe; color: #1e40af; }
            .status.error { background: #fee2e2; color: #991b1b; }
            .status.success { background: #d1fae5; color: #065f46; }
            .status.info { background: #fef3c7; color: #92400e; }
            .stats {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 10px;
                margin-top: 20px;
            }
            .stat {
                background: #f9fafb;
                padding: 12px;
                border-radius: 8px;
                text-align: center;
            }
            .stat-label { font-size: 12px; color: #6b7280; margin-bottom: 4px; }
            .stat-value { font-size: 18px; font-weight: 700; color: #667eea; }
            .loader {
                display: inline-block;
                width: 14px;
                height: 14px;
                border: 2px solid rgba(255,255,255,0.3);
                border-top-color: white;
                border-radius: 50%;
                animation: spin 0.6s linear infinite;
            }
            @keyframes spin { to { transform: rotate(360deg); } }
            .examples {
                margin-top: 20px;
                padding: 16px;
                background: #f9fafb;
                border-radius: 8px;
            }
            .examples h3 {
                font-size: 14px;
                color: #374151;
                margin-bottom: 10px;
            }
            .example-link {
                display: inline-block;
                margin: 4px;
                padding: 6px 12px;
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                font-size: 12px;
                color: #667eea;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            .example-link:hover {
                background: #667eea;
                color: white;
                border-color: #667eea;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎬 Universal Video Proxy</h1>
                <p>Vidmoly (HLS) + SendVid (MP4) - Auto-détection</p>
            </div>
            <div class="content">
                <div class="input-section">
                    <input 
                        type="text" 
                        id="urlInput" 
                        class="url-input" 
                        placeholder="Collez l'URL Vidmoly ou SendVid ici..."
                    >
                </div>
                
                <div class="examples">
                    <h3>📌 Exemples :</h3>
                    <span class="example-link" onclick="loadExample('vidmoly')">Vidmoly</span>
                    <span class="example-link" onclick="loadExample('sendvid')">SendVid</span>
                </div>
                
                <div class="video-container">
                    <video id="videoPlayer" controls></video>
                </div>
                
                <div class="controls">
                    <button onclick="loadVideoFromUrl()">▶️ Charger</button>
                    <button onclick="downloadVideo()" id="downloadBtn" disabled>⬇️ Télécharger</button>
                    <button onclick="clearProgress()">🗑️ Effacer progression</button>
                    <button onclick="location.reload()">🔄 Recharger</button>
                </div>
                
                <div id="status" class="status">
                    ⏳ Collez une URL Vidmoly ou SendVid pour commencer
                </div>
                
                <div class="stats" id="stats" style="display:none">
                    <div class="stat">
                        <div class="stat-label">Type</div>
                        <div class="stat-value" id="playerType">-</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Position</div>
                        <div class="stat-value" id="position">0:00</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Durée</div>
                        <div class="stat-value" id="duration">-:--</div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            const videoPlayer = document.getElementById('videoPlayer');
            const urlInput = document.getElementById('urlInput');
            const statusDiv = document.getElementById('status');
            const statsDiv = document.getElementById('stats');
            const downloadBtn = document.getElementById('downloadBtn');
            
            let hls = null;
            let currentVideoKey = null;
            let currentPlayerType = null;
            let saveProgressInterval = null;
            
            function setStatus(message, type = '') {
                statusDiv.innerHTML = message;
                statusDiv.className = 'status ' + type;
            }
            
            function formatTime(seconds) {
                const mins = Math.floor(seconds / 60);
                const secs = Math.floor(seconds % 60);
                return `${mins}:${secs.toString().padStart(2, '0')}`;
            }
            
            function loadExample(type) {
                if (type === 'vidmoly') {
                    urlInput.value = 'https://vidmoly.net/embed-y2dfh1ndem54.html';
                } else if (type === 'sendvid') {
                    urlInput.value = 'https://sendvid.com/embed/e47tdkrv';
                }
                loadVideoFromUrl();
            }
            
            async function saveProgress() {
                if (!videoPlayer.duration || videoPlayer.paused || !currentVideoKey) return;
                
                try {
                    await fetch('/api/progress', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            video_key: currentVideoKey,
                            current_time: videoPlayer.currentTime,
                            duration: videoPlayer.duration,
                            timestamp: new Date().toISOString()
                        })
                    });
                } catch (error) {
                    console.error('Erreur sauvegarde:', error);
                }
            }
            
            async function loadProgress(videoKey) {
                try {
                    const response = await fetch(`/api/progress/${encodeURIComponent(videoKey)}`);
                    const data = await response.json();
                    
                    if (data.success && data.progress) {
                        return data.progress.current_time;
                    }
                } catch (error) {
                    console.error('Erreur chargement progression:', error);
                }
                return 0;
            }
            
            async function clearProgress() {
                if (!currentVideoKey) {
                    setStatus('❌ Aucune vidéo chargée', 'error');
                    return;
                }
                
                try {
                    await fetch(`/api/progress/${encodeURIComponent(currentVideoKey)}`, { method: 'DELETE' });
                    setStatus('🗑️ Progression effacée', 'success');
                    setTimeout(() => location.reload(), 1000);
                } catch (error) {
                    setStatus('❌ Erreur effacement', 'error');
                }
            }
            
            async function downloadVideo() {
                if (!currentVideoKey || !currentPlayerType) {
                    setStatus('❌ Aucune vidéo chargée', 'error');
                    return;
                }
                
                try {
                    downloadBtn.disabled = true;
                    downloadBtn.innerHTML = '⏳ Préparation...';
                    
                    setStatus('<span class="loader"></span> Préparation du téléchargement...', 'loading');
                    
                    // Demander le téléchargement au serveur
                    const response = await fetch(`/api/download/${encodeURIComponent(currentVideoKey)}`);
                    const data = await response.json();
                    
                    if (!data.success) {
                        setStatus('❌ Erreur: ' + data.error, 'error');
                        downloadBtn.disabled = false;
                        downloadBtn.innerHTML = '⬇️ Télécharger';
                        return;
                    }
                    
                    setStatus('📥 Téléchargement en cours...', 'loading');
                    
                    // Créer un lien de téléchargement
                    const downloadUrl = `/api/download/${encodeURIComponent(currentVideoKey)}/file`;
                    
                    // Créer un élément <a> invisible pour déclencher le téléchargement
                    const a = document.createElement('a');
                    a.href = downloadUrl;
                    a.download = `video_${currentVideoKey}.mp4`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    
                    setStatus('✅ Téléchargement démarré !', 'success');
                    
                    setTimeout(() => {
                        downloadBtn.disabled = false;
                        downloadBtn.innerHTML = '⬇️ Télécharger';
                    }, 2000);
                    
                } catch (error) {
                    setStatus('❌ Erreur téléchargement: ' + error.message, 'error');
                    downloadBtn.disabled = false;
                    downloadBtn.innerHTML = '⬇️ Télécharger';
                }
            }
            
            async function loadVideoFromUrl() {
                const url = urlInput.value.trim();
                
                if (!url) {
                    setStatus('❌ Veuillez coller une URL', 'error');
                    return;
                }
                
                try {
                    setStatus('<span class="loader"></span> Détection du type de lecteur...', 'loading');
                    
                    const infoResponse = await fetch('/api/info', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ url: url })
                    });
                    
                    const info = await infoResponse.json();
                    
                    if (!info.success) {
                        setStatus('❌ Erreur: ' + info.error, 'error');
                        return;
                    }
                    
                    currentVideoKey = info.video_key;
                    currentPlayerType = info.player_type;
                    const playerType = info.player_type.toUpperCase();
                    
                    // Activer le bouton de téléchargement
                    downloadBtn.disabled = false;
                    
                    document.getElementById('playerType').textContent = playerType;
                    statsDiv.style.display = 'grid';
                    
                    const savedTime = await loadProgress(currentVideoKey);
                    
                    if (savedTime > 0) {
                        setStatus(`📌 Reprise ${playerType} à ${formatTime(savedTime)}...`, 'info');
                    } else {
                        setStatus(`<span class="loader"></span> Chargement ${playerType}...`, 'loading');
                    }
                    
                    const streamUrl = `/api/stream/${encodeURIComponent(currentVideoKey)}`;
                    
                    if (info.player_type === 'vidmoly') {
                        // HLS avec HLS.js
                        if (Hls.isSupported()) {
                            if (hls) hls.destroy();
                            
                            hls = new Hls();
                            hls.loadSource(streamUrl);
                            hls.attachMedia(videoPlayer);
                            
                            hls.on(Hls.Events.MANIFEST_PARSED, () => {
                                if (savedTime > 0) {
                                    videoPlayer.currentTime = savedTime;
                                }
                                setStatus('✅ Vidéo HLS prête', 'success');
                                videoPlayer.play().catch(() => {});
                            });
                            
                            hls.on(Hls.Events.ERROR, (event, data) => {
                                if (data.fatal) {
                                    setStatus('❌ Erreur HLS: ' + data.type, 'error');
                                }
                            });
                        }
                    } else {
                        // MP4 direct
                        videoPlayer.src = streamUrl;
                        
                        videoPlayer.addEventListener('loadedmetadata', () => {
                            document.getElementById('duration').textContent = formatTime(videoPlayer.duration);
                            
                            if (savedTime > 0 && savedTime < videoPlayer.duration) {
                                videoPlayer.currentTime = savedTime;
                            }
                            
                            setStatus('✅ Vidéo MP4 prête', 'success');
                            videoPlayer.play().catch(() => {});
                        }, { once: true });
                    }
                    
                } catch (error) {
                    setStatus('❌ Erreur: ' + error.message, 'error');
                    console.error(error);
                }
            }
            
            videoPlayer.addEventListener('play', () => {
                if (saveProgressInterval) clearInterval(saveProgressInterval);
                saveProgressInterval = setInterval(saveProgress, 5000);
            });
            
            videoPlayer.addEventListener('pause', () => {
                saveProgress();
                if (saveProgressInterval) clearInterval(saveProgressInterval);
            });
            
            videoPlayer.addEventListener('timeupdate', () => {
                if (videoPlayer.duration) {
                    document.getElementById('position').textContent = formatTime(videoPlayer.currentTime);
                    document.getElementById('duration').textContent = formatTime(videoPlayer.duration);
                }
            });
            
            window.addEventListener('beforeunload', () => {
                saveProgress();
            });
            
            urlInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    loadVideoFromUrl();
                }
            });
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/api/info', methods=['POST'])
def get_info():
    """Obtenir les infos sur la vidéo (auto-détection du type)"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'success': False, 'error': 'URL manquante'}), 400
        
        # Détecter le type de lecteur
        player_type, video_id = parse_video_url(url)
        
        if not player_type:
            return jsonify({
                'success': False,
                'error': 'Type de lecteur non supporté. Utilisez Vidmoly ou SendVid'
            }), 400
        
        print(f"\n🎯 Type détecté: {player_type.upper()} | ID: {video_id}")
        
        video_key = f"{player_type}_{video_id}"
        
        if player_type == 'vidmoly':
            # Traitement Vidmoly (HLS)
            embed_url = f"https://vidmoly.net/embed-{video_id}.html"
            m3u8_url = extract_vidmoly_m3u8(embed_url)
            
            if not m3u8_url:
                return jsonify({'success': False, 'error': 'M3U8 non trouvé'}), 404
            
            playlist_url, playlist = get_vidmoly_segment_playlist(m3u8_url)
            
            if not playlist or not playlist.segments:
                return jsonify({'success': False, 'error': 'Aucun segment trouvé'}), 500
            
            app.config[f'video_{video_key}'] = {
                'player_type': 'vidmoly',
                'url': playlist_url,
                'playlist': playlist,
                'video_id': video_id
            }
            
            return jsonify({
                'success': True,
                'player_type': 'vidmoly',
                'video_key': video_key,
                'segments': len(playlist.segments),
                'duration': sum(seg.duration for seg in playlist.segments if seg.duration)
            })
        
        elif player_type == 'sendvid':
            # Traitement SendVid (MP4)
            embed_url = f"https://sendvid.com/embed/{video_id}"
            video_url = extract_sendvid_video(embed_url)
            
            if not video_url:
                return jsonify({'success': False, 'error': 'Vidéo non trouvée'}), 404
            
            video_info = get_sendvid_info(video_url)
            
            app.config[f'video_{video_key}'] = {
                'player_type': 'sendvid',
                'url': video_info['url'],
                'info': video_info,
                'video_id': video_id
            }
            
            return jsonify({
                'success': True,
                'player_type': 'sendvid',
                'video_key': video_key,
                'size': video_info['size'],
                'supports_range': video_info['accepts_range']
            })
        
    except Exception as e:
        print(f"❌ Erreur API info: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stream/<video_key>')
def stream_video(video_key):
    """Stream la vidéo (HLS ou MP4 selon le type)"""
    try:
        video_data = app.config.get(f'video_{video_key}')
        
        if not video_data:
            return "Info non chargée", 404
        
        player_type = video_data['player_type']
        
        if player_type == 'vidmoly':
            # Proxy HLS
            playlist_url = video_data['url']
            playlist = video_data['playlist']
            video_id = video_data['video_id']
            
            base_url = playlist_url.rsplit('/', 1)[0] + '/'
            
            new_manifest = "#EXTM3U\n"
            new_manifest += "#EXT-X-VERSION:3\n"
            new_manifest += f"#EXT-X-TARGETDURATION:{int(max(seg.duration for seg in playlist.segments if seg.duration) + 1)}\n"
            new_manifest += "#EXT-X-MEDIA-SEQUENCE:0\n\n"
            
            for i, segment in enumerate(playlist.segments):
                if segment.uri.startswith('http'):
                    segment_url = segment.uri
                else:
                    segment_url = urljoin(base_url, segment.uri)
                
                app.config[f'segment_{video_key}_{i}'] = segment_url
                
                new_manifest += f"#EXTINF:{segment.duration},\n"
                new_manifest += f"/api/segment/{video_key}/{i}\n"
            
            new_manifest += "#EXT-X-ENDLIST\n"
            
            return Response(
                new_manifest,
                mimetype='application/vnd.apple.mpegurl',
                headers={'Cache-Control': 'no-cache'}
            )
        
        elif player_type == 'sendvid':
            # Proxy MP4
            video_url = video_data['url']
            video_info = video_data['info']
            
            range_header = request.headers.get('Range')
            
            if range_header and video_info['accepts_range']:
                headers = session.headers.copy()
                headers['Range'] = range_header
                
                response = session.get(video_url, headers=headers, stream=True, timeout=30)
                
                def generate():
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                
                return Response(
                    generate(),
                    status=response.status_code,
                    mimetype=video_info['type'],
                    headers={
                        'Content-Range': response.headers.get('Content-Range', ''),
                        'Content-Length': response.headers.get('Content-Length', ''),
                        'Accept-Ranges': 'bytes'
                    }
                )
            else:
                response = session.get(video_url, stream=True, timeout=30)
                
                def generate():
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                
                return Response(
                    generate(),
                    mimetype=video_info['type'],
                    headers={
                        'Content-Length': str(video_info['size']) if video_info['size'] > 0 else '',
                        'Accept-Ranges': 'bytes'
                    }
                )
        
    except Exception as e:
        print(f"❌ Erreur stream: {e}")
        import traceback
        traceback.print_exc()
        return str(e), 500

@app.route('/api/segment/<video_key>/<int:segment_num>')
def proxy_segment(video_key, segment_num):
    """Proxy un segment vidéo (Vidmoly uniquement)"""
    try:
        segment_url = app.config.get(f'segment_{video_key}_{segment_num}')
        
        if not segment_url:
            return "Segment introuvable", 404
        
        response = session.get(segment_url, timeout=15, stream=True)
        
        if response.status_code == 200:
            def generate():
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            
            return Response(
                generate(),
                mimetype='video/mp2t',
                headers={'Cache-Control': 'public, max-age=3600'}
            )
        
        return f"Erreur: {response.status_code}", response.status_code
        
    except Exception as e:
        print(f"❌ Erreur segment: {e}")
        return str(e), 500

@app.route('/api/progress', methods=['POST'])
def save_progress_endpoint():
    """Sauvegarde la progression"""
    try:
        data = request.get_json()
        video_key = data.get('video_key')
        
        if not video_key:
            return jsonify({'success': False, 'error': 'video_key manquant'}), 400
        
        success = save_progress(video_key, data)
        return jsonify({'success': success})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/progress/<video_key>', methods=['GET'])
def get_progress_endpoint(video_key):
    """Récupère la progression"""
    try:
        progress = get_progress(video_key)
        
        if progress:
            print(f"📖 Progression: {video_key} @ {progress.get('current_time')}s")
        
        return jsonify({'success': True, 'progress': progress})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/progress/<video_key>', methods=['DELETE'])
def delete_progress_endpoint(video_key):
    """Efface la progression"""
    try:
        progress = load_progress()
        
        if video_key in progress:
            del progress[video_key]
            
            with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(progress, f, indent=2, ensure_ascii=False)
            
            print(f"🗑️ Progression effacée: {video_key}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/download/<video_key>')
def prepare_download(video_key):
    """Prépare le téléchargement de la vidéo"""
    try:
        video_data = app.config.get(f'video_{video_key}')
        
        if not video_data:
            return jsonify({'success': False, 'error': 'Vidéo non chargée'}), 404
        
        player_type = video_data['player_type']
        
        # Stocker les infos de téléchargement
        app.config[f'download_{video_key}'] = {
            'player_type': player_type,
            'ready': True
        }
        
        return jsonify({
            'success': True,
            'player_type': player_type,
            'message': 'Prêt pour le téléchargement'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/download/<video_key>/file')
def download_file(video_key):
    """
    Télécharge la vidéo complète
    - Pour SendVid (MP4) : Stream direct du fichier
    - Pour Vidmoly (HLS) : Concatène tous les segments en un seul fichier
    """
    try:
        video_data = app.config.get(f'video_{video_key}')
        
        if not video_data:
            return "Vidéo non trouvée", 404
        
        player_type = video_data['player_type']
        
        print(f"\n📥 Téléchargement demandé: {video_key} ({player_type})")
        
        if player_type == 'sendvid':
            # SendVid: Stream direct du MP4
            video_url = video_data['url']
            video_info = video_data['info']
            
            print(f"⬇️ Téléchargement MP4 depuis: {video_url}")
            
            response = session.get(video_url, stream=True, timeout=30)
            
            def generate():
                bytes_downloaded = 0
                for chunk in response.iter_content(chunk_size=65536):  # 64KB chunks
                    if chunk:
                        bytes_downloaded += len(chunk)
                        if bytes_downloaded % (1024 * 1024 * 10) == 0:  # Log tous les 10MB
                            print(f"📦 Téléchargé: {bytes_downloaded / (1024*1024):.1f}MB")
                        yield chunk
                print(f"✅ Téléchargement terminé: {bytes_downloaded / (1024*1024):.1f}MB")
            
            return Response(
                generate(),
                mimetype='video/mp4',
                headers={
                    'Content-Disposition': f'attachment; filename="video_{video_key}.mp4"',
                    'Content-Type': 'video/mp4',
                    'Content-Length': str(video_info['size']) if video_info['size'] > 0 else ''
                }
            )
        
        elif player_type == 'vidmoly':
            # Vidmoly: Option 1 avec FFmpeg (conversion en MP4) ou Option 2 sans (concat .ts)
            playlist = video_data['playlist']
            playlist_url = video_data['url']
            base_url = playlist_url.rsplit('/', 1)[0] + '/'
            
            print(f"⬇️ Téléchargement HLS: {len(playlist.segments)} segments")
            
            if FFMPEG_AVAILABLE:
                # Méthode avec FFmpeg : Conversion HLS → MP4
                print("🎬 Conversion HLS → MP4 avec FFmpeg")
                
                # Créer un fichier temporaire pour la liste des segments
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    concat_file = f.name
                    
                    # Télécharger tous les segments dans un dossier temporaire
                    temp_dir = tempfile.mkdtemp()
                    
                    for i, segment in enumerate(playlist.segments):
                        try:
                            if segment.uri.startswith('http'):
                                segment_url = segment.uri
                            else:
                                segment_url = urljoin(base_url, segment.uri)
                            
                            segment_path = os.path.join(temp_dir, f'segment_{i:04d}.ts')
                            
                            response = session.get(segment_url, timeout=15)
                            
                            if response.status_code == 200:
                                with open(segment_path, 'wb') as sf:
                                    sf.write(response.content)
                                
                                # Ajouter à la liste concat
                                f.write(f"file '{segment_path}'\n")
                                
                                if i % 10 == 0:
                                    print(f"📦 Téléchargé: {i+1}/{len(playlist.segments)} segments")
                            else:
                                print(f"⚠️ Erreur segment {i}: {response.status_code}")
                        
                        except Exception as e:
                            print(f"❌ Erreur segment {i}: {e}")
                
                print(f"✅ Tous les segments téléchargés, conversion en MP4...")
                
                # Convertir avec FFmpeg
                output_file = os.path.join(temp_dir, 'output.mp4')
                
                try:
                    subprocess.run([
                        'ffmpeg',
                        '-f', 'concat',
                        '-safe', '0',
                        '-i', concat_file,
                        '-c', 'copy',
                        '-bsf:a', 'aac_adtstoasc',
                        output_file
                    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    print(f"✅ Conversion terminée: {os.path.getsize(output_file) / (1024*1024):.1f}MB")
                    
                    # Stream le fichier MP4
                    def generate():
                        with open(output_file, 'rb') as f:
                            while True:
                                chunk = f.read(65536)
                                if not chunk:
                                    break
                                yield chunk
                        
                        # Nettoyer après l'envoi
                        try:
                            os.unlink(concat_file)
                            os.unlink(output_file)
                            for file in os.listdir(temp_dir):
                                os.unlink(os.path.join(temp_dir, file))
                            os.rmdir(temp_dir)
                            print("🗑️ Fichiers temporaires nettoyés")
                        except:
                            pass
                    
                    return Response(
                        generate(),
                        mimetype='video/mp4',
                        headers={
                            'Content-Disposition': f'attachment; filename="video_{video_key}.mp4"',
                            'Content-Type': 'video/mp4',
                            'Content-Length': str(os.path.getsize(output_file))
                        }
                    )
                
                except subprocess.CalledProcessError as e:
                    print(f"❌ Erreur FFmpeg: {e}")
                    # Nettoyer
                    try:
                        os.unlink(concat_file)
                        for file in os.listdir(temp_dir):
                            os.unlink(os.path.join(temp_dir, file))
                        os.rmdir(temp_dir)
                    except:
                        pass
                    
                    return "Erreur de conversion FFmpeg", 500
            
            else:
                # Méthode sans FFmpeg : Concaténation simple en .ts
                print("⚠️ FFmpeg non disponible, téléchargement en .ts")
                
                def generate():
                    bytes_downloaded = 0
                    for i, segment in enumerate(playlist.segments):
                        try:
                            if segment.uri.startswith('http'):
                                segment_url = segment.uri
                            else:
                                segment_url = urljoin(base_url, segment.uri)
                            
                            response = session.get(segment_url, timeout=15)
                            
                            if response.status_code == 200:
                                data = response.content
                                bytes_downloaded += len(data)
                                
                                if i % 10 == 0:
                                    print(f"📦 Segment {i+1}/{len(playlist.segments)} - {bytes_downloaded / (1024*1024):.1f}MB")
                                
                                yield data
                            else:
                                print(f"⚠️ Erreur segment {i}: {response.status_code}")
                        
                        except Exception as e:
                            print(f"❌ Erreur segment {i}: {e}")
                    
                    print(f"✅ Téléchargement terminé: {bytes_downloaded / (1024*1024):.1f}MB")
                
                return Response(
                    generate(),
                    mimetype='video/mp2t',
                    headers={
                        'Content-Disposition': f'attachment; filename="video_{video_key}.ts"',
                        'Content-Type': 'video/mp2t'
                    }
                )
        
    except Exception as e:
        print(f"❌ Erreur téléchargement: {e}")
        import traceback
        traceback.print_exc()
        return str(e), 500

@app.route('/health')
def health():
    """Health check"""
    return jsonify({'status': 'healthy'})

# ============================================
# DÉMARRAGE
# ============================================

if __name__ == '__main__':
    print("\n🚀 Serveur prêt!")
    print("📡 Accédez à: http://localhost:5000")
    print("🎯 Collez une URL Vidmoly ou SendVid")
    print("⚠️  USAGE PRIVÉ UNIQUEMENT\n")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )
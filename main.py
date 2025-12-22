"""
main.py - Point d'entrée AnimeZone OPTIMISÉ
Combine app.py (backend) + routes.py (frontend)
"""

import os
import logging
from app import create_app
from routes import register_frontend_routes

logger = logging.getLogger(__name__)

# ==================
# CRÉATION APP COMPLÈTE
# ==================

def create_full_app():
    """Crée l'app complète avec backend + frontend"""
    
    # 1. Créer le backend (DB + cache)
    app = create_app()
    logger.info("✅ Backend initialisé")
    
    # 2. Ajouter les routes frontend
    register_frontend_routes(app)
    logger.info("✅ Frontend initialisé")
    
    # 3. Stats
    logger.info(f"📊 {len(app.url_map._rules)} routes enregistrées")
    
    return app


# ==================
# POINT D'ENTRÉE
# ==================

if __name__ == '__main__':
    app = create_full_app()
    
    print("\n" + "="*60)
    print("🚀 AnimeZone - OPTIMISÉ v2.0")
    print("📍 http://localhost:8080")
    print(f"📊 {len(app.url_map._rules)} routes disponibles")
    print("="*60)
    print("🔥 Optimisations:")
    print("  ✅ Cache JSON en mémoire (rechargé 1x au démarrage)")
    print("  ✅ Recherche O(1) au lieu de O(n)")
    print("  ✅ Indexes DB sur colonnes critiques")
    print("  ✅ Queries limitées + batch")
    print("  ✅ Architecture 2 fichiers (app.py + routes.py)")
    print("="*60 + "\n")
    
    port = int(os.environ.get('PORT', 8080))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=True,
        use_reloader=False,  # Important: évite le double chargement
        threaded=True
    )
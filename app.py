"""
Application principale Flask pour AnimeZone
Version avec Application Factory
"""

import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialisation des extensions
db = SQLAlchemy()
login_manager = LoginManager()

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
    
    # Créer les modèles et les tables
    with app.app_context():
        # Importer la fonction de création des modèles
        from models import create_models
        
        # Créer les modèles avec db
        User, UserProgress, UserFavorite = create_models(db)
        
        # Rendre les modèles accessibles globalement dans l'app
        app.User = User
        app.UserProgress = UserProgress
        app.UserFavorite = UserFavorite
        
        # User loader pour Flask-Login
        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))
        
        # Créer les tables
        db.create_all()
        logger.info("✅ Base de données initialisée")
    
    # Importer et enregistrer les routes
    from routes import register_routes
    register_routes(app)
    
    logger.info(f"✅ {len(app.url_map._rules)} routes enregistrées")
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    print("\n" + "="*60)
    print("🚀 AnimeZone - Mode Dataset Local")
    print("📍 http://localhost:8080")
    print(f"📊 {len(app.url_map._rules)} routes disponibles")
    print("="*60 + "\n")
    
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
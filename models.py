"""
Modèles de données pour AnimeZone
User, UserProgress, UserFavorite
"""

import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# db est initialisé dans app.py et sera accessible via l'import
# On ne l'importe pas ici pour éviter l'import circulaire

def create_models(db):
    """
    Crée et retourne les modèles de données
    Cette fonction est appelée depuis app.py après l'initialisation de db
    """
    
    class User(UserMixin, db.Model):
        """Modèle utilisateur"""
        __tablename__ = 'user'
        
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(64), unique=True, nullable=False)
        password_hash = db.Column(db.String(256), nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
        last_login = db.Column(db.DateTime, default=datetime.datetime.utcnow)

        def set_password(self, password):
            """Définit le mot de passe hashé"""
            self.password_hash = generate_password_hash(password)

        def check_password(self, password):
            """Vérifie le mot de passe"""
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
        last_watched = db.Column(db.DateTime, default=datetime.datetime.utcnow)

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
        added_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

        user = db.relationship('User', backref=db.backref('favorites', lazy='dynamic'))

        __table_args__ = (
            db.UniqueConstraint('user_id', 'anime_id'),
        )
    
    return User, UserProgress, UserFavorite
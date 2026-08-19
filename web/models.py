from app import db
from datetime import datetime, timezone
from sqlalchemy import func

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    discord_id = db.Column(db.String(64), unique=True, nullable=False)
    username = db.Column(db.String(64), nullable=False)
    discriminator = db.Column(db.String(4))
    avatar = db.Column(db.String(128))
    access_token = db.Column(db.String(256))
    refresh_token = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    servers = db.relationship('UserServer', back_populates='user', lazy='dynamic')

class Server(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    discord_id = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    icon = db.Column(db.String(128))
    owner_id = db.Column(db.String(64))
    member_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_analyzed = db.Column(db.DateTime)
    
    # Relationships
    users = db.relationship('UserServer', back_populates='server', lazy='dynamic')
    vibe_scores = db.relationship('VibeScore', back_populates='server', lazy='dynamic')
    analytics = db.relationship('ServerAnalytics', back_populates='server', lazy='dynamic')

class UserServer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    permissions = db.Column(db.Integer, default=0)
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = db.relationship('User', back_populates='servers')
    server = db.relationship('Server', back_populates='users')

class VibeScore(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    overall_score = db.Column(db.Float, default=0.0)
    activity_score = db.Column(db.Float, default=0.0)
    positivity_score = db.Column(db.Float, default=0.0)
    engagement_score = db.Column(db.Float, default=0.0)
    growth_score = db.Column(db.Float, default=0.0)
    calculated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    server = db.relationship('Server', back_populates='vibe_scores')

class ServerAnalytics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    message_count = db.Column(db.Integer, default=0)
    active_users = db.Column(db.Integer, default=0)
    new_members = db.Column(db.Integer, default=0)
    reactions_count = db.Column(db.Integer, default=0)
    voice_minutes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    server = db.relationship('Server', back_populates='analytics')

class ChannelActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    channel_id = db.Column(db.String(64), nullable=False)
    channel_name = db.Column(db.String(128), nullable=False)
    channel_type = db.Column(db.String(32), default='text')  # text, voice, category
    message_count = db.Column(db.Integer, default=0)
    last_activity = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

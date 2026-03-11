# 数据库模型
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    """用户模型"""
    __tablename__ = 'user'
    
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # 关系
    queries = db.relationship('QueryHistory', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.username}>'


class QueryHistory(db.Model):
    """查询历史模型"""
    __tablename__ = 'query_history'
    
    query_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    user_input = db.Column(db.Text, nullable=False)
    intent = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(50), nullable=False)
    query_time = db.Column(db.DateTime, default=datetime.utcnow)
    response = db.Column(db.Text)
    
    def __repr__(self):
        return f'<QueryHistory {self.query_id}>'


class WeatherCache(db.Model):
    """天气数据缓存模型"""
    __tablename__ = 'weather_cache'
    
    weather_id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False)
    temperature = db.Column(db.Float)
    temp_max = db.Column(db.Float)
    temp_min = db.Column(db.Float)
    weather = db.Column(db.String(50))
    humidity = db.Column(db.Float)
    wind_speed = db.Column(db.Float)
    wind_direction = db.Column(db.String(50))
    rain_probability = db.Column(db.Float)
    pressure = db.Column(db.Float)
    visibility = db.Column(db.Float)
    uv_index = db.Column(db.Float)
    update_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<WeatherCache {self.city} {self.date}>'

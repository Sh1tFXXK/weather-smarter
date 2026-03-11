# 配置文件
import os
from datetime import timedelta

# Flask配置
class Config:
    """基础配置"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-2026'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///weather.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 天气API配置
    # 使用高德天气API (需要申请API key: https://lbs.amap.com/api/webservice/guide/api/weatherinfo)
    # 或使用其他免费API如: OpenWeatherMap, 心知天气等
    WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY') or 'YOUR_API_KEY_HERE'
    WEATHER_API_URL = 'https://restapi.amap.com/v3/weather/weatherInfo'
    
    # 应用配置
    JSON_AS_ASCII = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    TESTING = False

# 配置字典
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

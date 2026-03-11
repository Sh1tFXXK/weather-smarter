# 数据库模块初始化
from .models import db, User, QueryHistory, WeatherCache

__all__ = ['db', 'User', 'QueryHistory', 'WeatherCache']

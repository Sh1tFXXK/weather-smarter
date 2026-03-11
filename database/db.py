# 数据库操作模块
from datetime import datetime
from .models import db, User, QueryHistory, WeatherCache


class DatabaseHandler:
    """数据库处理器"""
    
    @staticmethod
    def save_query(user_id: int, user_input: str, intent: str, location: str, response: str = None) -> QueryHistory:
        """
        保存查询记录
        
        Args:
            user_id: 用户ID
            user_input: 用户输入
            intent: 识别的意图
            location: 城市位置
            response: 系统响应
            
        Returns:
            QueryHistory对象
        """
        query = QueryHistory(
            user_id=user_id,
            user_input=user_input,
            intent=intent,
            location=location,
            response=response
        )
        db.session.add(query)
        db.session.commit()
        return query
    
    @staticmethod
    def save_weather_cache(city: str, date: str, weather_data: dict) -> WeatherCache:
        """
        缓存天气数据
        
        Args:
            city: 城市名
            date: 日期
            weather_data: 天气数据字典
            
        Returns:
            WeatherCache对象
        """
        weather = WeatherCache(
            city=city,
            date=date,
            temperature=weather_data.get('temperature'),
            temp_max=weather_data.get('temp_max'),
            temp_min=weather_data.get('temp_min'),
            weather=weather_data.get('weather'),
            humidity=weather_data.get('humidity'),
            wind_speed=weather_data.get('wind_speed'),
            wind_direction=weather_data.get('wind_direction'),
            rain_probability=weather_data.get('rain_probability'),
            pressure=weather_data.get('pressure'),
            visibility=weather_data.get('visibility'),
            uv_index=weather_data.get('uv_index'),
        )
        db.session.add(weather)
        db.session.commit()
        return weather
    
    @staticmethod
    def get_cached_weather(city: str, date: str) -> WeatherCache:
        """
        获取缓存的天气数据
        
        Args:
            city: 城市名
            date: 日期
            
        Returns:
            WeatherCache对象或None
        """
        return WeatherCache.query.filter_by(city=city, date=date).first()
    
    @staticmethod
    def get_user_query_history(user_id: int, limit: int = 10) -> list:
        """
        获取用户的查询历史
        
        Args:
            user_id: 用户ID
            limit: 限制数量
            
        Returns:
            查询历史列表
        """
        return QueryHistory.query.filter_by(user_id=user_id).order_by(
            QueryHistory.query_time.desc()
        ).limit(limit).all()

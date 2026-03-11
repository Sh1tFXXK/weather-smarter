# 天气API接口模块
import requests
import json
from typing import Dict, Any, Optional
from datetime import datetime
import time

class WeatherService:
    """天气服务"""
    
    def __init__(self, api_key: str = None, use_mock: bool = True):
        """
        初始化天气服务
        
        Args:
            api_key: 天气API密钥
            use_mock: 是否使用模拟数据
        """
        self.api_key = api_key
        self.use_mock = use_mock
        self.cached_data = {}
    
    def get_weather(self, city: str, date: str = 'today') -> Dict[str, Any]:
        """
        获取天气信息
        
        Args:
            city: 城市名称
            date: 日期 ('today', 'tomorrow'等)
            
        Returns:
            天气数据字典
        """
        if self.use_mock:
            return self._get_mock_weather(city, date)
        
        # 实际API调用（需要配置API key）
        try:
            return self._call_real_api(city)
        except Exception as e:
            print(f"天气API调用失败: {e}")
            return self._get_mock_weather(city, date)
    
    def _get_mock_weather(self, city: str, date: str = 'today') -> Dict[str, Any]:
        """获取模拟天气数据"""
        # 模拟数据库，存储多个城市的天气数据
        mock_data = {
            '太原': {
                'today': {
                    'city': '太原',
                    'date': '2026-03-11',
                    'temperature': 12,  # 摄氏度
                    'temp_max': 18,
                    'temp_min': 8,
                    'weather': '多云',
                    'weather_code': '4',
                    'humidity': 65,  # 湿度百分比
                    'wind_speed': 15,  # km/h
                    'wind_direction': '西北风',
                    'rain_probability': 0.2,  # 降雨概率
                    'visibility': 10,  # 能见度 km
                    'pressure': 1013,  # 气压 hPa
                    'uv_index': 3,  # 紫外线指数
                },
                'tomorrow': {
                    'city': '太原',
                    'date': '2026-03-12',
                    'temperature': 14,
                    'temp_max': 20,
                    'temp_min': 9,
                    'weather': '晴天',
                    'weather_code': '1',
                    'humidity': 55,
                    'wind_speed': 12,
                    'wind_direction': '北风',
                    'rain_probability': 0.1,
                    'visibility': 12,
                    'pressure': 1015,
                    'uv_index': 4,
                }
            },
            '北京': {
                'today': {
                    'city': '北京',
                    'date': '2026-03-11',
                    'temperature': 15,
                    'temp_max': 22,
                    'temp_min': 10,
                    'weather': '晴天',
                    'weather_code': '1',
                    'humidity': 45,
                    'wind_speed': 18,
                    'wind_direction': '东北风',
                    'rain_probability': 0.05,
                    'visibility': 15,
                    'pressure': 1012,
                    'uv_index': 5,
                }
            },
            '上海': {
                'today': {
                    'city': '上海',
                    'date': '2026-03-11',
                    'temperature': 16,
                    'temp_max': 20,
                    'temp_min': 12,
                    'weather': '阴天',
                    'weather_code': '3',
                    'humidity': 72,
                    'wind_speed': 20,
                    'wind_direction': '东风',
                    'rain_probability': 0.4,
                    'visibility': 8,
                    'pressure': 1010,
                    'uv_index': 2,
                }
            }
        }
        
        # 返回相应城市和日期的数据
        if city in mock_data:
            if date in mock_data[city]:
                return mock_data[city][date]
            else:
                # 返回今天的数据
                return mock_data[city].get('today', mock_data[city])
        
        # 如果城市不在列表中，返回默认数据
        return {
            'city': city,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'temperature': 15,
            'temp_max': 20,
            'temp_min': 10,
            'weather': '晴天',
            'weather_code': '1',
            'humidity': 60,
            'wind_speed': 15,
            'wind_direction': '北风',
            'rain_probability': 0.15,
            'visibility': 10,
            'pressure': 1013,
            'uv_index': 3,
        }
    
    def _call_real_api(self, city: str) -> Dict[str, Any]:
        """调用真实天气API（示例：使用心知天气或高德地图API）"""
        # 这是一个示例实现，实际使用需要：
        # 1. 注册API账号并获取API Key
        # 2. 配置基础URL
        # 3. 处理API响应
        
        # 示例: 使用高德地图API
        amap_url = "https://restapi.amap.com/v3/weather/weatherInfo"
        params = {
            'city': city,
            'key': self.api_key,
            'extensions': 'all'
        }
        
        response = requests.get(amap_url, params=params, timeout=5)
        data = response.json()
        
        if data.get('status') == '1':
            # 处理API返回的数据
            # 具体处理逻辑根据API文档调整
            return data
        else:
            raise Exception(f"API返回错误: {data.get('info')}")

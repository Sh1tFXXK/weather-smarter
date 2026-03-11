# 信息抽取模块
import re
from typing import Dict, Any, List

class EntityExtractor:
    """实体抽取器"""
    
    # 城市名称列表（示例，可扩展）
    CITIES = [
        '北京', '上海', '广州', '深圳', '杭州', '武汉', '西安', '南京',
        '重庆', '成都', '苏州', '长沙', '郑州', '天津', '青岛', '太原',
        '山西', '河南', '河北', '江苏', '浙江', '福建', '广东', '江西'
    ]
    
    # 生活场景关键词
    SCENARIOS = {
        'outdoor_activity': ['户外', '运动', '散步', '骑车', '跑步', '爬山', '踏青'],
        'travel': ['出行', '旅游', '郊游', '短途', '长途', '自驾', '旅行'],
        'daily_life': ['上班', '工作', '上学', '逛街', '购物', '聚餐', '聚会'],
        'special_event': ['婚礼', '派对', '演唱会', '比赛', '展会', '开会'],
    }
    
    # 服装类型
    CLOTHES = ['短袖', '长袖', '短裤', '长裤', '穿衣', '衣服', '风衣', '外套', '西装', '夹克']
    
    # 天气指标
    WEATHER_INDICATORS = ['温度', '气温', '风速', '降雨', '降雨量', '湿度', '气压', '紫外线']
    
    def __init__(self):
        """初始化抽取器"""
        pass
    
    def extract(self, text: str) -> Dict[str, Any]:
        """
        从文本中抽取关键实体
        
        Args:
            text: 用户输入文本
            
        Returns:
            包含抽取实体的字典
        """
        entities = {
            'location': self._extract_location(text),
            'scenario': self._extract_scenario(text),
            'clothing_needed': self._check_clothing_advice(text),
            'rain_concern': self._check_rain_concern(text),
            'weather_indicators': self._extract_weather_indicators(text),
        }
        return entities
    
    def _extract_location(self, text: str) -> str:
        """抽取地点信息"""
        for city in self.CITIES:
            if city in text:
                return city
        return '太原'  # 默认城市
    
    def _extract_scenario(self, text: str) -> str:
        """抽取生活场景"""
        for scenario, keywords in self.SCENARIOS.items():
            if any(keyword in text for keyword in keywords):
                return scenario
        return 'daily_life'
    
    def _check_clothing_advice(self, text: str) -> bool:
        """检查是否需要穿衣建议"""
        return any(word in text for word in self.CLOTHES)
    
    def _check_rain_concern(self, text: str) -> bool:
        """检查是否关心下雨情况"""
        rain_keywords = ['雨', '降雨', '下雨', '雨具', '雨伞', '雨衣', '防水']
        return any(keyword in text for keyword in rain_keywords)
    
    def _extract_weather_indicators(self, text: str) -> List[str]:
        """抽取天气指标"""
        indicators = []
        for indicator in self.WEATHER_INDICATORS:
            if indicator in text:
                indicators.append(indicator)
        return indicators if indicators else ['temperature', 'weather']

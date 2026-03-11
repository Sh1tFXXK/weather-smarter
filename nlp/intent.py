# 意图识别模块
import re
from typing import Tuple, Dict, Any

class IntentClassifier:
    """意图分类器"""
    
    # 定义意图和关键词映射
    INTENT_KEYWORDS = {
        'weather_query': ['天气', '气温', '温度', '风速', '降雨', '湿度', '天晴', '下雨', '晴天', '阴天', '多云'],
        'suitable_travel': ['适合', '出行', '旅游', '外出', '散步', '郊游', '野餐', '应该', '能否'],
        'rain_related': ['雨具', '雨伞', '雨衣', '需要', '带', '下雨', '降水', '降雨'],
        'sport_activity': ['运动', '跑步', '散步', '骑车', '打球', '户外', '适合'],
        'clothing_advice': ['穿衣', '穿什么', '衣服', '外套', '夹克', '短袖', '建议'],
        'location_query': ['哪里', '城市', '地点', '地区', '北京', '上海', '深圳', '广州', '太原', '山西'],
    }
    
    # 时间相关关键词
    TIME_KEYWORDS = {
        'today': ['今天', '今日', '现在', '此时'],
        'tomorrow': ['明天', '明日', '后天'],
        'future': ['这周', '周末', '下周', '本周', '接下来', '未来'],
    }
    
    def __init__(self):
        """初始化分类器"""
        self.intents = list(self.INTENT_KEYWORDS.keys())
    
    def classify(self, text: str) -> Tuple[str, float, Dict[str, Any]]:
        """
        分类用户意图
        
        Args:
            text: 用户输入文本
            
        Returns:
            (intent, confidence, extra_info)
        """
        text = text.lower()
        
        # 计算每个意图的匹配分数
        intent_scores = {}
        for intent, keywords in self.INTENT_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in text)
            intent_scores[intent] = score
        
        # 获取最高分数的意图
        if max(intent_scores.values()) == 0:
            return 'general_query', 0.5, {'raw_text': text}
        
        best_intent = max(intent_scores, key=intent_scores.get)
        score = intent_scores[best_intent]
        confidence = min(score / 3, 1.0)  # 归一化置信度
        
        # 识别时间信息
        time_info = self._extract_time_info(text)
        
        extra_info = {
            'raw_text': text,
            'time': time_info,
            'all_scores': intent_scores
        }
        
        return best_intent, confidence, extra_info
    
    def _extract_time_info(self, text: str) -> str:
        """提取时间信息"""
        for time_type, keywords in self.TIME_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                return time_type
        return 'today'

# 回复生成模块
from typing import Dict, Any, List

class ResponseGenerator:
    """自然语言回复生成器"""
    
    def generate_response(self, intent: str, decisions: Dict[str, Any], weather_data: Dict[str, Any]) -> str:
        """
        生成自然语言回复
        
        Args:
            intent: 用户意图
            decisions: 决策引擎的输出
            weather_data: 天气数据
            
        Returns:
            自然语言回复字符串
        """
        response_parts = []
        
        # 添加主要建议
        if decisions.get('suggestions'):
            response_parts.extend(decisions['suggestions'])
        
        # 添加防范措施
        if decisions.get('precautions'):
            response_parts.append('\n防范措施:')
            response_parts.extend(decisions['precautions'])
        
        # 添加具体建议
        if decisions.get('recommendations'):
            response_parts.append('\n详细信息:')
            response_parts.extend(decisions['recommendations'])
        
        # 拼接最终回复
        response = '\n'.join(response_parts)
        return response
    
    def format_weather_summary(self, weather_data: Dict[str, Any], location: str) -> str:
        """
        格式化天气摘要
        
        Args:
            weather_data: 天气数据
            location: 地点
            
        Returns:
            格式化的天气摘要
        """
        summary = f"""
【{location}天气摘要】
日期: {weather_data.get('date', '未知')}
天气: {weather_data.get('weather', '未知')}
温度: {weather_data.get('temperature', '--')}°C (最高:{weather_data.get('temp_max', '--')}°C / 最低:{weather_data.get('temp_min', '--')}°C)
风力: {weather_data.get('wind_direction', '--')} {weather_data.get('wind_speed', '--')}km/h
湿度: {weather_data.get('humidity', '--')}%
降雨概率: {weather_data.get('rain_probability', 0)*100:.0f}%
紫外线指数: {weather_data.get('uv_index', '--')}
"""
        return summary.strip()
    
    def generate_quick_answer(self, weather_data: Dict[str, Any], intent: str) -> str:
        """
        生成快速回答
        
        Args:
            weather_data: 天气数据
            intent: 用户意图
            
        Returns:
            快速回答
        """
        temp = weather_data.get('temperature', 15)
        weather = weather_data.get('weather', '晴朗')
        
        quick_answers = {
            'weather_query': f'当前{weather}，气温{temp}°C。',
            'suitable_travel': f'当前天气{weather}，气温{temp}°C，' + 
                             ('适合出行。' if 5 <= temp <= 28 else '不太适合出行。'),
            'rain_related': f'降雨概率{weather_data.get("rain_probability", 0)*100:.0f}%。',
            'sport_activity': f'气温{temp}°C，' + 
                            ('适合户外运动。' if 8 <= temp <= 25 else '不适合户外运动。'),
            'clothing_advice': self._get_clothing_advice(temp),
        }
        
        return quick_answers.get(intent, f'天气{weather}，气温{temp}°C。')
    
    def _get_clothing_advice(self, temp: float) -> str:
        """根据温度获取穿衣建议"""
        if temp < 0:
            return '天气寒冷，建议穿厚羽绒服。'
        elif temp < 5:
            return '天气较冷，建议穿着厚毛衣和外套。'
        elif temp < 12:
            return '天气凉爽，建议穿着秋冬外套。'
        elif temp < 18:
            return '天气温暖，建议穿着薄外套。'
        elif temp < 25:
            return '天气舒适，可穿短袖衫。'
        else:
            return '天气炎热，建议穿着清爽衣物。'
    
    def format_error_response(self, error_msg: str) -> str:
        """格式化错误回复"""
        return f'抱歉，处理请求时出现错误: {error_msg}\n请稍后重试或更换提问方式。'

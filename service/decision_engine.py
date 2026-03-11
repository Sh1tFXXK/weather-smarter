# 生活决策规则模块
from typing import Dict, Any, List, Tuple

class DecisionEngine:
    """生活决策引擎"""
    
    def __init__(self):
        """初始化决策引擎"""
        self.rules = self._init_rules()
    
    def _init_rules(self) -> Dict[str, Any]:
        """初始化规则库"""
        return {
            'travel': {
                'suitable_temp_range': (5, 28),
                'max_wind_speed': 40,
                'max_rain_probability': 0.3,
                'min_visibility': 5,
            },
            'outdoor_sports': {
                'suitable_temp_range': (8, 25),
                'max_wind_speed': 25,
                'max_rain_probability': 0.1,
                'min_visibility': 8,
            },
            'daily_work': {
                'suitable_temp_range': (-10, 35),
                'max_wind_speed': 60,
                'max_rain_probability': 1.0,
                'min_visibility': 1,
            }
        }
    
    def make_decision(self, intent: str, weather_data: Dict[str, Any], entities: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据意图、天气数据和实体信息做出生活决策
        
        Args:
            intent: 用户意图
            weather_data: 天气数据
            entities: 抽取的实体
            
        Returns:
            包含建议的决策字典
        """
        decisions = {
            'suggestions': [],
            'precautions': [],
            'recommendations': [],
        }
        
        # 根据不同意图生成建议
        if 'travel' in intent or 'suitable_travel' in intent:
            decisions = self._travel_decision(weather_data, entities, decisions)
        elif 'sport' in intent or 'sport_activity' in intent:
            decisions = self._sport_decision(weather_data, entities, decisions)
        elif 'rain' in intent or 'rain_related' in intent:
            decisions = self._rain_decision(weather_data, entities, decisions)
        elif 'clothing' in intent or 'clothing_advice' in intent:
            decisions = self._clothing_decision(weather_data, entities, decisions)
        else:
            decisions = self._general_decision(weather_data, entities, decisions)
        
        # 添加通用建议
        decisions = self._add_general_advice(weather_data, decisions)
        
        return decisions
    
    def _travel_decision(self, weather: Dict, entities: Dict, decisions: Dict) -> Dict:
        """出行决策"""
        temp = weather.get('temperature', 15)
        wind = weather.get('wind_speed', 0)
        rain_prob = weather.get('rain_probability', 0)
        
        rules = self.rules['travel']
        
        # 判断是否适合出行
        temp_ok = rules['suitable_temp_range'][0] <= temp <= rules['suitable_temp_range'][1]
        wind_ok = wind <= rules['max_wind_speed']
        rain_ok = rain_prob <= rules['max_rain_probability']
        
        if temp_ok and wind_ok and rain_ok:
            decisions['suggestions'].append('✓ 天气不错，非常适合出行！')
        else:
            decisions['suggestions'].append('⚠ 当前天气条件一般，建议谨慎出行。')
            
            if not temp_ok:
                if temp < rules['suitable_temp_range'][0]:
                    decisions['precautions'].append(f'🥶 温度较低({temp}°C)，建议穿着厚重衣物。')
                else:
                    decisions['precautions'].append(f'🔥 温度较高({temp}°C)，建议穿着清爽衣物和防晒。')
            
            if not rain_ok:
                decisions['precautions'].append(f'☔ 有{rain_prob*100:.0f}%的降雨概率，建议携带雨伞。')
            
            if not wind_ok:
                decisions['precautions'].append(f'💨 风力较大({wind}km/h)，建议选择避风地点。')
        
        # 具体建议
        decisions['recommendations'].append(f'当前温度: {temp}°C，{weather.get("weather", "晴朗")}')
        if rain_prob > 0.3:
            decisions['recommendations'].append(f'降雨概率: {rain_prob*100:.0f}%，请携带雨具。')
        
        return decisions
    
    def _sport_decision(self, weather: Dict, entities: Dict, decisions: Dict) -> Dict:
        """运动决策"""
        temp = weather.get('temperature', 15)
        wind = weather.get('wind_speed', 0)
        rain_prob = weather.get('rain_probability', 0)
        humidity = weather.get('humidity', 60)
        
        rules = self.rules['outdoor_sports']
        
        # 判断是否适合户外运动
        temp_ok = rules['suitable_temp_range'][0] <= temp <= rules['suitable_temp_range'][1]
        wind_ok = wind <= rules['max_wind_speed']
        rain_ok = rain_prob <= rules['max_rain_probability']
        humidity_ok = humidity < 85
        
        if temp_ok and wind_ok and rain_ok and humidity_ok:
            decisions['suggestions'].append('✓ 天气条件优秀，非常适合户外运动！')
        else:
            decisions['suggestions'].append('⚠ 当前天气不太适合户外运动。')
            
            if not temp_ok:
                decisions['precautions'].append(f'温度({temp}°C)不适合运动，请选择室内运动。')
            
            if humidity > 85:
                decisions['precautions'].append(f'👔 湿度较高({humidity}%)，容易出汗，建议准备干爽衣物。')
            
            if not rain_ok:
                decisions['precautions'].append('❌ 有降雨，不建议户外运动。')
        
        decisions['recommendations'].append(f'体感温度: {temp}°C，湿度: {humidity}%')
        
        return decisions
    
    def _rain_decision(self, weather: Dict, entities: Dict, decisions: Dict) -> Dict:
        """下雨相关决策"""
        rain_prob = weather.get('rain_probability', 0)
        
        if rain_prob > 0.7:
            decisions['suggestions'].append('⚠️ 降雨概率很高，出门必须携带雨具！')
            decisions['precautions'].append('建议携带防水背包和雨鞋。')
        elif rain_prob > 0.4:
            decisions['suggestions'].append('☔ 有中等降雨概率，建议携带雨伞。')
        elif rain_prob > 0.1:
            decisions['suggestions'].append('💧 有小概率降雨，可备好雨具以备不时之需。')
        else:
            decisions['suggestions'].append('✓ 降雨概率低，无需担心。')
        
        decisions['recommendations'].append(f'降雨概率: {rain_prob*100:.0f}%')
        
        return decisions
    
    def _clothing_decision(self, weather: Dict, entities: Dict, decisions: Dict) -> Dict:
        """穿衣建议"""
        temp = weather.get('temperature', 15)
        wind = weather.get('wind_speed', 0)
        humidity = weather.get('humidity', 60)
        
        # 根据温度给出穿衣建议
        if temp < 0:
            decisions['suggestions'].append('🥶 极寒: 建议穿着厚羽绒服、保暖裤、围巾、手套和帽子。')
        elif temp < 5:
            decisions['suggestions'].append('❄️  寒冷: 建议穿着厚毛衣、外套、长裤。')
        elif temp < 12:
            decisions['suggestions'].append('🧥 凉爽: 建议穿着秋冬外套、长袖衫、长裤。')
        elif temp < 18:
            decisions['suggestions'].append('👕 温暖: 建议穿着薄外套或卫衣、长裤或牛仔裤。')
        elif temp < 25:
            decisions['suggestions'].append('🌤️  舒适: 建议穿着短袖衫、短裤或裙子。')
        else:
            decisions['suggestions'].append('☀️  炎热: 建议穿着透气短装，做好防晒。')
        
        if wind > 25:
            decisions['recommendations'].append(f'💨 风力大({wind}km/h)，建议加一件挡风外套。')
        
        if humidity > 80:
            decisions['recommendations'].append('💧 空气潮湿，选择吸湿排汗的面料。')
        
        return decisions
    
    def _general_decision(self, weather: Dict, entities: Dict, decisions: Dict) -> Dict:
        """通用决策"""
        temp = weather.get('temperature', 15)
        condition = weather.get('weather', '晴朗')
        rain_prob = weather.get('rain_probability', 0)
        
        decisions['suggestions'].append(f'当前天气: {condition}，气温{temp}°C。')
        
        if rain_prob > 0.5:
            decisions['recommendations'].append('建议携带雨伞出门。')
        
        return decisions
    
    def _add_general_advice(self, weather: Dict, decisions: Dict) -> Dict:
        """添加通用建议"""
        uv_index = weather.get('uv_index', 3)
        
        if uv_index > 6:
            decisions['recommendations'].append('☀️ 紫外线指数较高，外出请做好防晒。')
        
        return decisions

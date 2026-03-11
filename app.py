# Flask应用主程序
import os
from flask import Flask, render_template, request, jsonify
from config.config import config
from nlp.intent import IntentClassifier
from nlp.entity_extract import EntityExtractor
from service.weather_api import WeatherService
from service.decision_engine import DecisionEngine
from utils.response import ResponseGenerator
from database.models import db
from database.db import DatabaseHandler
from datetime import datetime

# 初始化Flask应用
app = Flask(__name__)

# 加载配置
config_name = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config[config_name])

# 初始化数据库
db.init_app(app)

# 初始化各个模块
intent_classifier = IntentClassifier()
entity_extractor = EntityExtractor()
weather_service = WeatherService(use_mock=True)  # 开发环境使用模拟数据
decision_engine = DecisionEngine()
response_generator = ResponseGenerator()

# 创建应用上下文
with app.app_context():
    db.create_all()


@app.route('/')
def index():
    """主页路由"""
    return render_template('index.html')


@app.route('/api/query', methods=['POST'])
def query():
    """
    处理用户自然语言查询
    
    请求数据:
    {
        "user_input": "明天太原天气怎么样？"
    }
    
    返回:
    {
        "status": "success",
        "intent": "weather_query",
        "location": "太原",
        "weather_summary": "...",
        "response": "..."
    }
    """
    try:
        data = request.get_json()
        user_input = data.get('user_input', '').strip()
        
        if not user_input:
            return jsonify({
                'status': 'error',
                'message': '请输入有效的问题'
            }), 400
        
        # 1. 意图识别
        intent, confidence, extra_info = intent_classifier.classify(user_input)
        
        # 2. 实体抽取
        entities = entity_extractor.extract(user_input)
        location = entities.get('location', '太原')
        time_info = extra_info.get('time', 'today')
        
        # 3. 获取天气数据
        weather_data = weather_service.get_weather(location, time_info)
        
        # 4. 构建决策
        decisions = decision_engine.make_decision(intent, weather_data, entities)
        
        # 5. 生成回复
        response = response_generator.generate_response(intent, decisions, weather_data)
        weather_summary = response_generator.format_weather_summary(weather_data, location)
        
        return jsonify({
            'status': 'success',
            'intent': intent,
            'confidence': confidence,
            'location': location,
            'weather_summary': weather_summary,
            'response': response,
            'entities': entities,
        })
    
    except Exception as e:
        print(f"错误: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'处理请求失败: {str(e)}'
        }), 500


@app.route('/api/quick-query', methods=['POST'])
def quick_query():
    """快速查询接口"""
    try:
        data = request.get_json()
        location = data.get('location', '太原')
        
        # 获取天气数据
        weather_data = weather_service.get_weather(location, 'today')
        
        return jsonify({
            'status': 'success',
            'location': location,
            'weather_data': weather_data,
            'quick_answer': response_generator.generate_quick_answer(weather_data, 'weather_query')
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/weather/<city>', methods=['GET'])
def get_weather(city):
    """获取指定城市的天气"""
    try:
        weather_data = weather_service.get_weather(city, 'today')
        return jsonify({
            'status': 'success',
            'location': city,
            'weather': weather_data
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat()
    })


@app.errorhandler(404)
def not_found(error):
    """404错误处理"""
    return jsonify({
        'status': 'error',
        'message': '请求的资源不存在'
    }), 404


@app.errorhandler(500)
def server_error(error):
    """500错误处理"""
    return jsonify({
        'status': 'error',
        'message': '服务器内部错误'
    }), 500


if __name__ == '__main__':
    # 开发环境运行
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=True
    )

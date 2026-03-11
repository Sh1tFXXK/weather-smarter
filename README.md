# 天气智能服务系统 (Weather Smart Service System)

## 📋 项目概述

这是一个面向生活决策的自然语言交互式天气服务系统，基于太原学院智能科学与技术专业毕业论文项目。

**核心功能：**
- 🎯 自然语言理解：识别用户意图，抽取关键实体
- 🌡️ 智能天气查询：获取实时天气数据和预报信息
- 💡 生活决策支持：根据天气提供出行、运动、穿衣等生活建议
- 💬 自然语言回复：生成友好的生活建议和预警信息

## 🏗️ 项目架构

```
用户输入(自然语言)
        ↓
[自然语言处理层] - 意图识别 + 信息抽取
        ↓
[业务逻辑层] - 调用天气API + 决策规则
        ↓
[数据服务层] - 天气数据 + 缓存
        ↓
[表现层] - 生成自然语言回复
        ↓
用户(决策建议)
```

## 📁 项目结构

```
weather_decision_system/
├── app.py                      # Flask应用入口
├── config/
│   └── config.py              # 配置文件(API key、数据库等)
├── nlp/
│   ├── intent.py              # 意图识别模块
│   └── entity_extract.py      # 实体抽取模块
├── service/
│   ├── weather_api.py         # 天气接口调用
│   └── decision_engine.py     # 生活决策规则引擎
├── database/
│   ├── models.py              # SQLAlchemy数据模型
│   └── db.py                  # 数据库操作函数
├── utils/
│   └── response.py            # 自然语言回复生成
├── templates/
│   └── index.html             # 前端主页面
├── static/
│   ├── css/
│   │   └── style.css          # 样式表
│   └── js/
│       └── script.js          # 前端JavaScript
├── requirements.txt           # Python依赖包
├── README.md                  # 项目说明(本文件)
└── .gitignore                # Git忽略配置
```

## 🚀 快速开始

### 1. 环境准备

**系统要求：**
- Python 3.8+
- pip 包管理器

**虚拟环境设置：**
```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置应用

在项目根目录创建 `.env` 文件(可选)：
```env
FLASK_ENV=development
FLASK_DEBUG=True
WEATHER_API_KEY=your_api_key_here
DATABASE_URL=sqlite:///weather.db
```

### 4. 运行应用

```bash
python app.py
```

应用将在 `http://localhost:5000` 启动

## 💻 API 接口

### 1. 自然语言查询接口

**请求：**
```http
POST /api/query
Content-Type: application/json

{
    "user_input": "明天太原适合出行吗?"
}
```

**响应示例：**
```json
{
    "status": "success",
    "intent": "suitable_travel",
    "location": "太原",
    "confidence": 0.95,
    "weather_summary": "【太原天气摘要】...",
    "response": "✓ 天气不错，非常适合出行！...",
    "entities": {
        "location": "太原",
        "scenario": "travel",
        "rain_concern": true
    }
}
```

### 2. 快速查询接口

**请求：**
```http
POST /api/quick-query
Content-Type: application/json

{
    "location": "北京"
}
```

### 3. 获取城市天气

**请求：**
```http
GET /api/weather/北京
```

### 4. 健康检查

**请求：**
```http
GET /api/health
```

## 🎯 支持的用户意图

| 意图类型 | 示例问题 | 说明 |
|---------|--------|------|
| `weather_query` | "今天天气怎么样?" | 天气信息查询 |
| `suitable_travel` | "明天适合出行吗?" | 出行建议 |
| `rain_related` | "需要带雨伞吗?" | 降雨相关信息 |
| `sport_activity` | "适合户外运动吗?" | 运动建议 |
| `clothing_advice` | "今天穿什么?" | 穿衣建议 |
| `location_query` | "北京的天气?" | 特定地点天气 |

## 🌡️ 支持的城市

目前支持以下城市（可扩展）：
- 太原, 北京, 上海, 广州, 深圳
- 杭州, 武汉, 西安, 南京, 重庆
- 成都, 苏州, 长沙, 郑州, 天津
- 等等...

## 📊 系统决策规则

### 出行适宜性判断
```
适宜条件:
- 温度: 5°C ~ 28°C
- 风速: ≤ 40 km/h
- 降雨概率: ≤ 30%
- 能见度: ≥ 5 km
```

### 运动适宜性判断
```
适宜条件:
- 温度: 8°C ~ 25°C
- 风速: ≤ 25 km/h
- 降雨概率: ≤ 10%
- 湿度: < 85%
```

### 穿衣建议

| 温度范围 | 穿衣建议 |
|---------|--------|
| < 0°C | 厚羽绒服 + 保暖衣物 |
| 0 ~ 5°C | 厚毛衣 + 外套 |
| 5 ~ 12°C | 秋冬外套 + 长袖 |
| 12 ~ 18°C | 薄外套 + 长袖 |
| 18 ~ 25°C | 短袖 + 短裤/裙子 |
| > 25°C | 轻薄衣物 + 防晒 |

## 🔌 天气数据来源

当前MVP使用**模拟天气数据**进行演示。

**连接真实API选项：**
1. **高德地图API** - https://lbs.amap.com/
2. **心知天气** - https://www.seniverse.com/
3. **OpenWeatherMap** - https://openweathermap.org/
4. **中国气象局API** - http://www.cma.gov.cn/

配置步骤：
1. 注册API账号获取密钥
2. 在 `config/config.py` 中配置 `WEATHER_API_KEY`
3. 修改 `service/weather_api.py` 中的 `_call_real_api()` 方法
4. 在 `app.py` 中设置 `use_mock=False`

## 📈 自然语言处理流程

### 1. 意图识别 (Intent Classification)
使用**关键词匹配** + **置信度计算**：
- 遍历用户输入，统计意图关键词出现次数
- 计算置信度 = (关键词命中数 / 3)
- 返回最高分意图

```python
# 示例
Input: "明天太原适合出行吗?"
↓
关键词: ["适合"] → 意图权重 = 1
关键词: ["出行"] → 意图权重 = 1
↓
检测意图: suitable_travel, 置信度: 0.67
```

### 2. 实体抽取 (Entity Extraction)
抽取关键信息：
- **地点** (Location) - 城市名称
- **场景** (Scenario) - 日常、旅游、运动等
- **特殊关注** - 雨伞需求、穿衣建议等

```python
# 示例
Input: "今天北京需要带雨伞吗?"
↓
Location: "北京"
Rain_Concern: True
Time: "today"
```

### 3. 决策规则应用 (Rule-based Decision Making)
基于抽取的实体和天气数据，应用规则库生成建议：
```python
if intent == "suitable_travel":
    if temp in [5, 28] and wind <= 40 and rain_prob <= 0.3:
        suggestion = "✓ 适合出行"
    else:
        suggestion = "⚠ 不适合出行"
```

### 4. 自然语言生成 (Natural Language Generation)
将结构化决策转换为自然语言：

```python
decisions = {
    'suggestions': ['✓ 天气不错，非常适合出行！'],
    'precautions': ['携带防晒用品'],
    'recommendations': ['气温18°C，建议穿薄外套']
}
↓
response = "✓ 天气不错，非常适合出行！\n防范措施：\n携带防晒用品\n..."
```

## 🗄️ 数据库设计

### 用户表 (user)
```sql
CREATE TABLE user (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME
);
```

### 查询历史表 (query_history)
```sql
CREATE TABLE query_history (
    query_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    user_input TEXT NOT NULL,
    intent VARCHAR(50),
    location VARCHAR(50),
    query_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    response TEXT,
    FOREIGN KEY (user_id) REFERENCES user(user_id)
);
```

### 天气缓存表 (weather_cache)
```sql
CREATE TABLE weather_cache (
    weather_id INT PRIMARY KEY AUTO_INCREMENT,
    city VARCHAR(50),
    date DATE,
    temperature FLOAT,
    weather VARCHAR(50),
    humidity FLOAT,
    wind_speed FLOAT,
    rain_probability FLOAT,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 🧪 测试用例

### 出行查询
```
用户输入: "明天太原适合出行吗?"
意图识别: suitable_travel (67%)
地点: 太原
时间: tomorrow

预期响应:
- 天气适宜性评估
- 温度、风力、降雨概率提示
- 防范措施建议
- 出行装备提示
```

### 穿衣建议
```
用户输入: "今天应该穿什么?"
意图识别: clothing_advice (71%)
地点: 太原
时间: today

预期响应:
- 根据温度的穿衣建议
- 湿度考量
- 防晒提示(如适用)
```

### 降雨关注
```
用户输入: "北京会下雨吗?"
意图识别: rain_related (60%)
地点: 北京
时间: today

预期响应:
- 降雨概率
- 雨具建议
- 防水准备
```

## 🌟 核心特性

✅ **智能意图识别** - 理解用户真实需求
✅ **多维度天气分析** - 温度、风力、湿度、紫外线等
✅ **生活化建议生成** - 将气象数据转化为可行建议
✅ **自然语言回复** - 友好、易懂的中文回复
✅ **跨平台支持** - Web应用，可扩展至移动端
✅ **可扩展架构** - 易于集成更多功能

## 🔮 后续优化方向

### 短期计划
- [ ] 集成真实天气API（高德/心知）
- [ ] 添加用户登录注册功能
- [ ] 实现查询历史记录
- [ ] 完善错误处理和异常提示

### 中期计划
- [ ] 基于机器学习的意图识别(BERT/RNN)
- [ ] 多轮对话支持
- [ ] 语音输入支持
- [ ] 移动端应用(WeChat Mini Program)

### 长期计划
- [ ] 个性化推荐(用户行为学习)
- [ ] 社交分享功能
- [ ] 天气趋势预警
- [ ] 与日程管理集成

## 📚 相关技术栈

- **后端框架**: Flask 2.3
- **ORM**: SQLAlchemy
- **数据库**: SQLite (开发环境)
- **前端**: HTML5 + CSS3 + Vanilla JavaScript
- **NLP**: 规则基础 + 关键词匹配
- **API**: RESTful API

## 👤 作者信息

**学生**: 王创  
**学号**: 4202250202319  
**专业**: 智能科学与技术  
**班级**: 智能科学2203  
**指导教师**: 邸文奇  
**学院**: 太原学院 - 智能与信息工程系  

**毕业论文**  
**题目**: 面向生活决策的自然语言交互式天气服务系统设计与实现  
**类型**: 设计类  
**完成时间**: 2026年  

## 📄 许可证

本项目为太原学院毕业论文项目。仅供学习和研究使用。

## 🤝 贡献

欢迎提交Issue和Pull Request！

---

**最后更新**: 2026年3月11日  
**项目状态**: MVP版本开发中 🚀

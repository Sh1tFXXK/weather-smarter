# API 接口文档

## 基础URL
```
http://localhost:5000
```

## 端点列表

### 1. 自然语言查询 - POST /api/query

**描述**: 处理自然语言输入，返回智能建议

**请求示例**:
```json
POST /api/query
Content-Type: application/json

{
    "user_input": "明天太原适合出行吗?"
}
```

**成功响应 (200)**:
```json
{
    "status": "success",
    "intent": "suitable_travel",
    "confidence": 0.67,
    "location": "太原",
    "weather_summary": "【太原天气摘要】\n...",
    "response": "✓ 天气不错，非常适合出行！\n...",
    "entities": {
        "location": "太原",
        "scenario": "travel",
        "clothing_needed": false,
        "rain_concern": false,
        "weather_indicators": ["temperature", "weather"]
    }
}
```

**错误响应 (400/500)**:
```json
{
    "status": "error",
    "message": "请输入有效的问题"
}
```

---

### 2. 快速查询 - POST /api/quick-query

**描述**: 快速获取指定城市的天气信息

**请求示例**:
```json
POST /api/quick-query
Content-Type: application/json

{
    "location": "北京"
}
```

**响应示例**:
```json
{
    "status": "success",
    "location": "北京",
    "weather_data": {
        "city": "北京",
        "date": "2026-03-11",
        "temperature": 15,
        "temp_max": 22,
        "temp_min": 10,
        "weather": "晴天",
        "humidity": 45,
        "wind_speed": 18,
        "rain_probability": 0.05
    },
    "quick_answer": "当前晴天，气温15°C，适合出行。"
}
```

---

### 3. 获取城市天气 - GET /api/weather/{city}

**描述**: 获取指定城市的天气数据

**请求示例**:
```
GET /api/weather/北京
```

**响应示例**:
```json
{
    "status": "success",
    "location": "北京",
    "weather": {
        "city": "北京",
        "date": "2026-03-11",
        "temperature": 15,
        "temp_max": 22,
        "temp_min": 10,
        "weather": "晴天",
        "weather_code": "1",
        "humidity": 45,
        "wind_speed": 18,
        "wind_direction": "东北风",
        "rain_probability": 0.05,
        "visibility": 15,
        "pressure": 1012,
        "uv_index": 5
    }
}
```

---

### 4. 健康检查 - GET /api/health

**描述**: 检查服务器是否运行正常

**请求示例**:
```
GET /api/health
```

**响应示例**:
```json
{
    "status": "ok",
    "timestamp": "2026-03-11T10:30:45.123456"
}
```

---

## 意图类型说明

| 意图代码 | 中文名称 | 示例 |
|---------|---------|------|
| `weather_query` | 天气查询 | "今天天气怎么样?" |
| `suitable_travel` | 出行建议 | "适合出行吗?" |
| `rain_related` | 降雨信息 | "会下雨吗?" |
| `sport_activity` | 运动建议 | "适合运动吗?" |
| `clothing_advice` | 穿衣建议 | "穿什么?" |
| `location_query` | 地点查询 | "北京天气?" |
| `general_query` | 一般查询 | 其他类型的问题 |

---

## 错误代码

| 代码 | 说明 |
|-----|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 示例代码

### Python requests
```python
import requests
import json

url = "http://localhost:5000/api/query"
data = {
    "user_input": "明天太原适合出行吗?"
}

response = requests.post(url, json=data)
result = response.json()

print(result['response'])
```

### JavaScript fetch
```javascript
const url = "http://localhost:5000/api/query";
const data = {
    user_input: "明天太原适合出行吗?"
};

fetch(url, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
})
.then(response => response.json())
.then(data => console.log(data.response));
```

### cURL
```bash
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: application/json" \
  -d '{"user_input": "明天太原适合出行吗?"}'
```

---

## 响应数据字段说明

### weather_summary (天气摘要)
包含城市、日期、温度、天气现象等基本信息的格式化字符串。

### response (智能建议)
根据用户意图和天气数据生成的自然语言建议，分为以下部分：
- **建议** (suggestions) - 核心建议
- **防范措施** (precautions) - 需要注意的事项
- **详细信息** (recommendations) - 具体数据和补充信息

### entities (抽取的实体)
- `location` - 识别的城市
- `scenario` - 识别的应用场景
- `clothing_needed` - 是否涉及穿衣建议
- `rain_concern` - 是否关注降雨
- `weather_indicators` - 提取的天气指标

---

## 使用限制

- 单个请求的输入字符长度限制: 500字
- 单个IP的请求频率: 无限制(开发环境)
- 响应超时时间: 10秒

---

## 常见问题

**Q: 如何更换默认城市?**
A: 修改 `nlp/entity_extract.py` 中的 `CITIES` 列表或默认值。

**Q: 如何集成真实天气API?**
A: 参考 `service/weather_api.py` 中的 `_call_real_api()` 方法注释。

**Q: 如何自定义决策规则?**
A: 修改 `service/decision_engine.py` 中的规则条件。

---

最后更新: 2026年3月11日

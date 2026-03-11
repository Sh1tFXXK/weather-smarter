// JavaScript 前端脚本

// DOM 元素
const userInput = document.getElementById('userInput');
const submitBtn = document.getElementById('submitBtn');
const resultSection = document.getElementById('resultSection');
const loadingSpinner = document.getElementById('loadingSpinner');
const resultContent = document.getElementById('resultContent');
const errorContent = document.getElementById('errorContent');

// 事件监听
submitBtn.addEventListener('click', handleQuery);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        handleQuery();
    }
});

/**
 * 处理用户查询
 */
function handleQuery() {
    const input = userInput.value.trim();
    
    if (!input) {
        alert('请输入您的问题');
        return;
    }
    
    // 显示加载动画
    resultSection.style.display = 'block';
    loadingSpinner.style.display = 'block';
    resultContent.style.display = 'none';
    errorContent.style.display = 'none';
    submitBtn.disabled = true;
    
    // 发送查询请求
    fetch('/api/query', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            user_input: input
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            displayResults(data);
        } else {
            showError(data.message || '处理请求失败');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showError('网络错误，请检查连接后重试');
    })
    .finally(() => {
        loadingSpinner.style.display = 'none';
        submitBtn.disabled = false;
    });
}

/**
 * 显示查询结果
 */
function displayResults(data) {
    // 天气摘要
    document.getElementById('weatherSummary').textContent = data.weather_summary;
    
    // 意图和地点
    document.getElementById('intentType').textContent = formatIntent(data.intent);
    document.getElementById('location').textContent = data.location;
    
    // 智能建议
    document.getElementById('responseContent').textContent = data.response;
    
    // 实体信息（高级）
    const entities = data.entities;
    if (entities && Object.keys(entities).length > 0) {
        document.getElementById('entitiesSection').style.display = 'block';
        let entitiesHtml = '<ul style="list-style: none; padding-left: 0;">';
        
        if (entities.location) {
            entitiesHtml += `<li>📍 地点: ${entities.location}</li>`;
        }
        if (entities.scenario) {
            entitiesHtml += `<li>🎯 场景: ${entities.scenario}</li>`;
        }
        if (entities.weather_indicators && entities.weather_indicators.length > 0) {
            entitiesHtml += `<li>📊 天气指标: ${entities.weather_indicators.join(', ')}</li>`;
        }
        if (entities.clothing_needed) {
            entitiesHtml += `<li>👕 穿衣相关: 是</li>`;
        }
        if (entities.rain_concern) {
            entitiesHtml += `<li>☔ 降雨关注: 是</li>`;
        }
        
        entitiesHtml += '</ul>';
        document.getElementById('entitiesContent').innerHTML = entitiesHtml;
    } else {
        document.getElementById('entitiesSection').style.display = 'none';
    }
    
    resultContent.style.display = 'block';
}

/**
 * 显示错误信息
 */
function showError(message) {
    document.getElementById('errorMessage').textContent = message;
    errorContent.style.display = 'block';
    resultContent.style.display = 'none';
}

/**
 * 格式化意图显示
 */
function formatIntent(intent) {
    const intentMap = {
        'weather_query': '天气查询',
        'suitable_travel': '出行建议',
        'rain_related': '降雨信息',
        'sport_activity': '运动建议',
        'clothing_advice': '穿衣建议',
        'location_query': '地点查询',
        'general_query': '一般查询'
    };
    
    return intentMap[intent] || intent;
}

/**
 * 示例搜索
 */
function askExample(question) {
    userInput.value = question;
    handleQuery();
}

/**
 * 快速查询
 */
function quickQuery(city) {
    resultSection.style.display = 'block';
    loadingSpinner.style.display = 'block';
    resultContent.style.display = 'none';
    errorContent.style.display = 'none';
    
    fetch(`/api/weather/${city}`, {
        method: 'GET'
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // 构造显示数据
            const weather = data.weather;
            let weatherContent = `【${city}天气信息】\n`;
            weatherContent += `日期: ${weather.date || '未知'}\n`;
            weatherContent += `天气: ${weather.weather || '未知'}\n`;
            weatherContent += `温度: ${weather.temperature || '--'}°C\n`;
            weatherContent += `温度范围: ${weather.temp_min || '--'}°C ~ ${weather.temp_max || '--'}°C\n`;
            weatherContent += `风力: ${weather.wind_direction || '--'} ${weather.wind_speed || '--'}km/h\n`;
            weatherContent += `湿度: ${weather.humidity || '--'}%\n`;
            weatherContent += `降雨概率: ${(weather.rain_probability || 0) * 100 | 0}%`;
            
            document.getElementById('weatherSummary').textContent = weatherContent;
            document.getElementById('location').textContent = city;
            document.getElementById('intentType').textContent = '天气查询';
            document.getElementById('responseContent').textContent = '查询完成。以上是该城市当前的天气信息。';
            document.getElementById('entitiesSection').style.display = 'none';
            
            resultContent.style.display = 'block';
        } else {
            showError(data.message || '查询失败');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showError('网络错误，请稍后重试');
    })
    .finally(() => {
        loadingSpinner.style.display = 'none';
    });
}

// 页面加载完成后的初始化
document.addEventListener('DOMContentLoaded', () => {
    console.log('天气智能服务系统已就绪');
    // 自动聚焦输入框
    userInput.focus();
});

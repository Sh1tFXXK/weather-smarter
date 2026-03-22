from __future__ import annotations

import re
from typing import Dict, Optional


CITY_LIST = [
    "北京",
    "上海",
    "广州",
    "深圳",
    "杭州",
    "成都",
    "武汉",
    "西安",
    "南京",
    "重庆",
    "天津",
    "苏州",
    "长沙",
    "青岛",
    "厦门",
    "郑州",
]

DATE_KEYWORDS = {
    "今天": "today",
    "明天": "tomorrow",
    "后天": "day_after_tomorrow",
    "周末": "weekend",
    "今晚": "tonight",
    "早上": "morning",
    "上午": "morning",
    "下午": "afternoon",
    "晚上": "evening",
}

ACTIVITY_KEYWORDS = {
    "跑步": "running",
    "骑行": "cycling",
    "通勤": "commute",
    "出行": "travel",
    "出游": "travel",
    "洗车": "car_wash",
    "穿衣": "clothing",
    "钓鱼": "fishing",
    "运动": "sport",
    "徒步": "hiking",
}


def extract_slots(text: str) -> Dict[str, Optional[str]]:
    city = None
    for candidate in CITY_LIST:
        if candidate in text:
            city = candidate
            break

    if city is None:
        match = re.search(r"([\u4e00-\u9fff]{2,4})市", text)
        if match:
            city = match.group(1)

    date = None
    for keyword, value in DATE_KEYWORDS.items():
        if keyword in text:
            date = value
            break

    activity = None
    for keyword, value in ACTIVITY_KEYWORDS.items():
        if keyword in text:
            activity = value
            break

    return {
        "city": city,
        "date": date,
        "activity": activity,
    }

from __future__ import annotations

import json

from openai import OpenAI


def main() -> None:
    client = OpenAI(api_key="lm-studio", base_url="http://127.0.0.1:1234/v1")
    system_prompt = (
        "你是环境驱动决策系统的智能推理层。"
        "基于输入的环境数据与规则决策，生成更自然、可解释的建议。"
        "严格输出 JSON："
        '{"advice": "...", "riskLevel": "low|medium|high", '
        '"reasons": ["..."], "actions": ["..."]}'
        "。若无法改进，保持 base_decision。"
    )
    context = {
        "query": "明天北京适合跑步吗",
        "intent": "sport_decision",
        "locale": "zh-CN",
        "weather": {
            "status": "多云",
            "temperature": 15,
            "feels_like": 14,
            "humidity": 55,
            "wind_direction": "东风",
            "wind_power": "3级",
            "precipitation": 0,
            "uv": 2,
            "aqi": 56,
        },
        "environment": None,
        "base_decision": {
            "advice": "天气条件较好，适合户外运动。",
            "riskLevel": "low",
            "reasons": ["示例原因"],
            "actions": ["注意热身"],
        },
        "memory": [],
        "rag": [],
    }
    resp = client.chat.completions.create(
        model="qwen3-0.6b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
        temperature=0.2,
        max_tokens=300,
        response_format={"type": "json_object"},
    )
    print(resp)
    if resp.choices:
        print("CONTENT:", resp.choices[0].message.content)


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, List

from backend.agent.llm_router import enrich_decision, llm_enabled, llm_status
from backend.agent.planner import plan_with_llm
from backend.agent.tools.base import ToolRegistry
from backend.agent.trajectory import AgentResult, AgentStep


class AgentRunner:
    def __init__(self, *, tools: ToolRegistry, max_steps: int = 8) -> None:
        self.tools = tools
        self.max_steps = max_steps

    def _infer_plan(self, goal: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        lower = goal.lower()
        location_args = {
            "city": context.get("city"),
            "adcode": context.get("adcode"),
            "lat": context.get("lat"),
            "lon": context.get("lon"),
            "lang": context.get("lang", "zh"),
        }
        plan: List[Dict[str, Any]] = []
        if any(token in lower for token in ("天气", "weather", "通勤", "伞", "雨", "温度", "wind")):
            plan.append({"tool": "get_weather", "args": location_args})
        if any(token in lower for token in ("预报", "forecast", "明天", "小时", "降水概率", "pop")):
            plan.append(
                {
                    "tool": "get_forecast",
                    "args": {
                        **location_args,
                        "hours": context.get("hours", 24),
                        "days": context.get("days", 7),
                    },
                }
            )
        if any(token in lower for token in ("aqi", "空气", "污染", "雾霾")):
            plan.append({"tool": "get_aqi", "args": location_args})
        if context.get("session_id"):
            plan.append(
                {
                    "tool": "recall_memory",
                    "args": {
                        "session_id": context.get("session_id"),
                        "query": goal,
                        "limit": 6,
                    },
                }
            )
        if context.get("user_id"):
            plan.append({"tool": "get_user_profile", "args": {"user_id": context.get("user_id")}})
        if any(token in lower for token in ("健康", "哮喘", "过敏", "风湿", "health", "risk")):
            plan.append(
                {
                    "tool": "assess_health_risk",
                    "args": {"weather": "__from_weather__", "profile": "__from_profile__"},
                }
            )
        if any(token in lower for token in ("知识", "依据", "证据", "rag", "knowledge")):
            plan.append({"tool": "search_knowledge", "args": {"query": goal, "top_k": 5}})
        if any(token in lower for token in ("提醒", "任务", "task", "todo")) and context.get("scheduled_time"):
            plan.append(
                {
                    "tool": "create_task",
                    "args": {
                        "type": context.get("task_type", "general"),
                        "time": context.get("scheduled_time"),
                        "note": goal,
                    },
                }
            )
        if any(token in lower for token in ("股票", "板块", "市场", "stock", "market")):
            plan.append(
                {
                    "tool": "query_stock_impact",
                    "args": {
                        "region": context.get("region", "华东"),
                        "weather_signal": goal,
                        "horizon": context.get("horizon", "24h"),
                    },
                }
            )
        if not plan:
            plan.append({"tool": "search_knowledge", "args": {"query": goal, "top_k": 3}})

        unique_plan: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for item in plan:
            key = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                unique_plan.append(item)
        return unique_plan[: self.max_steps]

    def _resolve_deferred_args(
        self,
        args: Dict[str, Any],
        observations: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        resolved = dict(args)
        if resolved.get("weather") == "__from_weather__":
            resolved["weather"] = observations.get("get_weather", {})
        if resolved.get("profile") == "__from_profile__":
            resolved["profile"] = (observations.get("get_user_profile", {}) or {}).get("profile") or {}
        return resolved

    async def _finalize_answer(
        self,
        *,
        goal: str,
        context: Dict[str, Any],
        observations: Dict[str, Dict[str, Any]],
    ) -> str:
        weather = observations.get("get_weather", {})
        forecast = observations.get("get_forecast", {})
        profile = (observations.get("get_user_profile", {}) or {}).get("profile") or {}
        memory_items = (observations.get("recall_memory") or {}).get("items") or []
        rag_items = (observations.get("search_knowledge") or {}).get("items") or []
        health = observations.get("assess_health_risk") or {}

        reasons: List[str] = []
        if weather.get("weather"):
            reasons.append(
                f"{weather.get('city') or context.get('city') or '当前位置'}当前{weather.get('weather')}，"
                f"{weather.get('temperature')}℃，AQI {weather.get('aqi')}"
            )
        hourly = forecast.get("hourly") or []
        if hourly:
            pops = [item.get("pop") for item in hourly if item.get("pop") is not None]
            if pops:
                reasons.append(f"未来小时级降水概率峰值约 {round(max(float(v) for v in pops) * 100)}%")
        if health.get("riskLevel"):
            reasons.append(f"健康风险等级为 {health.get('riskLevel')}")
        if profile.get("conditions"):
            reasons.append(f"已纳入用户档案条件：{'、'.join(profile.get('conditions', [])[:4])}")
        if rag_items:
            reasons.append(f"知识库命中 {len(rag_items)} 条证据")
        if memory_items:
            reasons.append(f"已参考近期记忆 {len(memory_items)} 条")
        if not reasons:
            reasons.append("已按当前目标执行最小必要工具链")

        base_answer = "；".join(reasons)
        if llm_enabled():
            patch = await enrich_decision(
                intent="agent_run",
                query=goal,
                locale=context.get("locale", "zh-CN"),
                weather=weather,
                environment={"observations": observations},
                base_decision={
                    "advice": base_answer,
                    "riskLevel": health.get("riskLevel") or "low",
                    "reasons": reasons[:4],
                    "actions": [],
                },
                memory=memory_items,
                rag=rag_items,
            )
            if patch and patch.get("advice"):
                return str(patch["advice"])
        return base_answer

    async def run(self, goal: str, context: Dict[str, Any]) -> AgentResult:
        trajectory: List[AgentStep] = []
        observations: Dict[str, Dict[str, Any]] = {}
        plan = await plan_with_llm(goal, context, self.tools) or self._infer_plan(goal, context)

        for index, item in enumerate(plan, start=1):
            tool_name = item["tool"]
            args = self._resolve_deferred_args(item.get("args", {}), observations)
            trajectory.append(
                AgentStep(
                    step=len(trajectory) + 1,
                    type="thought",
                    title=f"Thought {index}",
                    content=f"为完成目标，调用 {tool_name}",
                    tool=tool_name,
                    args=args,
                )
            )
            trajectory.append(
                AgentStep(
                    step=len(trajectory) + 1,
                    type="action",
                    title=f"Action {index}",
                    content=f"执行 {tool_name}",
                    tool=tool_name,
                    args=args,
                )
            )
            observation = await self.tools.invoke(tool_name, args)
            observations[tool_name] = observation
            trajectory.append(
                AgentStep(
                    step=len(trajectory) + 1,
                    type="observation",
                    title=f"Observation {index}",
                    content=f"{tool_name} 返回 {list(observation.keys())[:6]}",
                    tool=tool_name,
                    args=args,
                    observation=observation,
                )
            )

        llm_ok, llm_reason = llm_status()
        if not llm_ok:
            trajectory.append(
                AgentStep(
                    step=len(trajectory) + 1,
                    type="thought",
                    title="LLM Fallback",
                    content=f"LLM 不可用，使用规则汇总结果: {llm_reason}",
                )
            )

        answer = await self._finalize_answer(goal=goal, context=context, observations=observations)
        trajectory.append(
            AgentStep(
                step=len(trajectory) + 1,
                type="final",
                title="Final",
                content=answer,
                answer=answer,
            )
        )
        return AgentResult(
            answer=answer,
            trajectory=trajectory,
            sources=sorted({str(item.get("source")) for item in observations.values() if item.get("source")}),
            toolsUsed=list(observations.keys()),
            sessionId=context.get("session_id"),
            userId=context.get("user_id"),
            traceId=context.get("trace_id"),
        )

    async def stream(self, goal: str, context: Dict[str, Any]) -> AsyncIterator[AgentStep]:
        observations: Dict[str, Dict[str, Any]] = {}
        step_no = 0
        plan = await plan_with_llm(goal, context, self.tools) or self._infer_plan(goal, context)
        for index, item in enumerate(plan, start=1):
            tool_name = item["tool"]
            args = self._resolve_deferred_args(item.get("args", {}), observations)
            step_no += 1
            yield AgentStep(
                step=step_no,
                type="thought",
                title=f"Thought {index}",
                content=f"为完成目标，调用 {tool_name}",
                tool=tool_name,
                args=args,
            )
            step_no += 1
            yield AgentStep(
                step=step_no,
                type="action",
                title=f"Action {index}",
                content=f"执行 {tool_name}",
                tool=tool_name,
                args=args,
            )
            observation = await self.tools.invoke(tool_name, args)
            observations[tool_name] = observation
            step_no += 1
            yield AgentStep(
                step=step_no,
                type="observation",
                title=f"Observation {index}",
                content=f"{tool_name} 返回 {list(observation.keys())[:6]}",
                tool=tool_name,
                args=args,
                observation=observation,
            )
        step_no += 1
        answer = await self._finalize_answer(goal=goal, context=context, observations=observations)
        yield AgentStep(
            step=step_no,
            type="final",
            title="Final",
            content=answer,
            answer=answer,
        )

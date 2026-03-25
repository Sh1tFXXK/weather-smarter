from backend.agent.health_profile_store import get_health_profile_store


def test_health_profile_store_roundtrip() -> None:
    store = get_health_profile_store()
    profile = store.upsert_profile(
        user_id="user-1",
        display_name="测试用户",
        identity_summary="通勤用户",
        preferences=["提前提醒", "简洁结论"],
        goals=["准时到达"],
        important_locations=["公司", "家"],
        work_context="工作日通勤",
        long_term_memory="经常在下雨前问通勤安排",
        conditions=["rheumatism"],
        note="test",
        consent=True,
        sensitivity={"humidity": 70},
    )
    assert profile["user_id"] == "user-1"
    assert profile["display_name"] == "测试用户"
    loaded = store.get_profile("user-1")
    assert loaded
    assert loaded["conditions"] == ["rheumatism"]
    assert loaded["preferences"] == ["提前提醒", "简洁结论"]
    assert loaded["important_locations"] == ["公司", "家"]
    assert loaded["sensitivity"]["humidity"] == 70
    assert store.delete_profile("user-1") is True

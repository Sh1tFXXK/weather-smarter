from backend.agent.health_profile_store import get_health_profile_store


def test_health_profile_store_roundtrip() -> None:
    store = get_health_profile_store()
    profile = store.upsert_profile(
        user_id="user-1",
        conditions=["rheumatism"],
        note="test",
        consent=True,
        sensitivity={"humidity": 70},
    )
    assert profile["user_id"] == "user-1"
    loaded = store.get_profile("user-1")
    assert loaded
    assert loaded["conditions"] == ["rheumatism"]
    assert loaded["sensitivity"]["humidity"] == 70
    assert store.delete_profile("user-1") is True

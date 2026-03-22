from backend.rag.retriever import RAGRetriever


def test_rag_retrieval() -> None:
    items = [
        {
            "id": "running",
            "title": "跑步适宜条件",
            "content": "温度适中且无降雨时适合跑步",
            "tags": ["sport", "running"],
            "domain": "health",
        },
        {
            "id": "car_wash",
            "title": "洗车建议",
            "content": "晴朗干燥时适合洗车",
            "tags": ["car_wash"],
            "domain": "life",
        },
    ]
    retriever = RAGRetriever(items)
    results = retriever.retrieve("今天适合跑步吗", top_k=1)
    assert results
    assert results[0]["id"] == "running"

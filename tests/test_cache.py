from customer_service_agent.cache import TTLCache


def test_ttl_cache_hits_and_misses():
    now = 1000.0
    cache = TTLCache[str](ttl_seconds=10, max_size=2, clock=lambda: now)

    assert cache.get("order:A1001", default=None) is None
    cache.set("order:A1001", "shipped")

    assert cache.get("order:A1001") == "shipped"
    stats = cache.stats()
    assert stats.hits == 1
    assert stats.misses == 1
    assert stats.size == 1


def test_ttl_cache_expires_entries():
    current_time = {"value": 1000.0}
    cache = TTLCache[str](ttl_seconds=5, max_size=2, clock=lambda: current_time["value"])
    cache.set("faq:refund", "refund policy")

    current_time["value"] = 1006.0

    assert cache.get("faq:refund", default=None) is None
    assert cache.stats().size == 0


def test_ttl_cache_evicts_oldest_entry_when_full():
    current_time = {"value": 1000.0}
    cache = TTLCache[str](ttl_seconds=30, max_size=2, clock=lambda: current_time["value"])
    cache.set("first", "1")
    current_time["value"] = 1001.0
    cache.set("second", "2")
    current_time["value"] = 1002.0

    cache.set("third", "3")

    assert cache.get("first", default=None) is None
    assert cache.get("second") == "2"
    assert cache.get("third") == "3"

from app.cost.cache import normalize_description, diagnosis_cache_key, TTLCache


def test_normalize_collapses_whitespace_and_case():
    assert normalize_description("  Insufficient   Balance ") == "insufficient balance"


def test_normalize_handles_none():
    assert normalize_description(None) == ""


def test_cache_key_is_deterministic_for_identical_inputs():
    k1 = diagnosis_cache_key("CODE", "issuer", "auth", "Insufficient Balance")
    k2 = diagnosis_cache_key("CODE", "issuer", "auth", "insufficient   balance")
    assert k1 == k2


def test_cache_key_differs_for_different_inputs():
    k1 = diagnosis_cache_key("CODE", "issuer", "auth", "insufficient balance")
    k2 = diagnosis_cache_key("CODE", "issuer", "auth", "card expired")
    assert k1 != k2


def test_ttl_cache_set_then_get_returns_value_and_counts_a_hit():
    cache = TTLCache(ttl_seconds=100)
    cache.set("k1", "v1", now=1000.0)
    result = cache.get("k1", now=1005.0)
    assert result == "v1"
    assert cache.hits == 1
    assert cache.misses == 0


def test_ttl_cache_missing_key_counts_a_miss():
    cache = TTLCache()
    result = cache.get("nope", now=1000.0)
    assert result is None
    assert cache.misses == 1


def test_ttl_cache_expired_entry_is_a_miss_and_evicted():
    cache = TTLCache(ttl_seconds=10)
    cache.set("k1", "v1", now=1000.0)
    result = cache.get("k1", now=1020.0)
    assert result is None
    assert cache.misses == 1
    assert cache.size() == 0


def test_ttl_cache_hit_rate_computed_correctly():
    cache = TTLCache()
    cache.set("k1", "v1", now=0.0)
    cache.get("k1", now=1.0)
    cache.get("k1", now=1.0)
    cache.get("k2", now=1.0)
    assert abs(cache.hit_rate - (2 / 3)) < 1e-9

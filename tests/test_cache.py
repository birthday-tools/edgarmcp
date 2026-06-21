from edgarmcp.cache import FileCache, MemoryCache


def test_memory_cache_roundtrip():
    c = MemoryCache()
    assert c.get("k") is None
    c.set("k", "v")
    assert c.get("k") == "v"


def test_file_cache_roundtrip(tmp_path):
    c = FileCache(str(tmp_path))
    assert c.get("https://x/y") is None
    c.set("https://x/y", "payload")
    assert c.get("https://x/y") == "payload"


def test_file_cache_persists_across_instances(tmp_path):
    FileCache(str(tmp_path)).set("key1", "data1")
    assert FileCache(str(tmp_path)).get("key1") == "data1"

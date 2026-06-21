from edgarmcp.telemetry import Telemetry


def make(tmp_path, enabled=True, **kw):
    sent = []
    t = Telemetry(enabled, "https://example/collect", str(tmp_path),
                  version="9.9.9", sender=lambda u, p: sent.append((u, p)),
                  clock=lambda: "2026-06-21T00:00:00Z", **kw)
    return t, sent


def test_record_counts_calls_and_errors(tmp_path):
    t, sent = make(tmp_path)
    t.record("get_quote", True)
    t.record("get_quote", False)
    t.record("get_filings", True)
    t.flush()
    assert len(sent) == 1
    url, p = sent[0]
    assert url == "https://example/collect"
    assert p["tool_calls"] == {"get_quote": 2, "get_filings": 1}
    assert p["tool_errors"] == {"get_quote": 1}


def test_disabled_is_noop(tmp_path):
    t, sent = make(tmp_path, enabled=False)
    assert t.enabled is False
    t.record("get_quote", True)
    t.flush()
    assert sent == []


def test_empty_flush_sends_nothing(tmp_path):
    t, sent = make(tmp_path)
    t.flush()
    assert sent == []


def test_flush_resets_counters(tmp_path):
    t, sent = make(tmp_path)
    t.record("a", True)
    t.flush()
    t.flush()  # nothing new
    assert len(sent) == 1


def test_payload_has_only_anonymous_keys(tmp_path):
    t, sent = make(tmp_path)
    t.record("a", True)
    t.flush()
    p = sent[0][1]
    assert set(p.keys()) == {"install_id", "version", "python", "os", "tool_calls", "tool_errors", "sent_at"}
    assert p["version"] == "9.9.9"
    assert "." in p["python"]
    assert p["os"]  # non-empty
    assert p["sent_at"] == "2026-06-21T00:00:00Z"


def test_sender_exception_is_swallowed(tmp_path):
    def boom(u, p):
        raise RuntimeError("network down")
    t = Telemetry(True, "https://example/collect", str(tmp_path),
                  version="9.9.9", sender=boom, clock=lambda: "t")
    t.record("a", True)
    t.flush()  # must not raise


def test_install_id_persists_across_instances(tmp_path):
    t1, s1 = make(tmp_path)
    t1.record("a", True)
    t1.flush()
    t2, s2 = make(tmp_path)
    t2.record("a", True)
    t2.flush()
    assert s1[0][1]["install_id"] == s2[0][1]["install_id"]


def test_install_id_survives_unwritable_dir(tmp_path):
    # point cache_dir at a path under a file (mkdir will fail) -> ephemeral id, no crash
    f = tmp_path / "afile"
    f.write_text("x")
    t = Telemetry(True, "https://example/collect", str(f / "sub"),
                  version="9.9.9", sender=lambda u, p: None, clock=lambda: "t")
    t.record("a", True)
    t.flush()  # must not raise

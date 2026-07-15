from __future__ import annotations

from smbagent.agents.negotiation import NegotiationAgent


def test_try_extract_done_returns_false_when_no_json():
    done, req = NegotiationAgent._try_extract_done("普通の日本語の返信です。")
    assert done is False
    assert req == {}


def test_try_extract_done_returns_false_when_json_lacks_done_flag():
    text = '```json\n{"requirements": {"goals": ["x"]}}\n```'
    done, req = NegotiationAgent._try_extract_done(text)
    assert done is False


def test_try_extract_done_returns_false_when_done_is_false():
    text = '```json\n{"done": false, "requirements": {"goals": ["x"]}}\n```'
    done, req = NegotiationAgent._try_extract_done(text)
    assert done is False


def test_try_extract_done_returns_payload_on_done_true():
    text = (
        "完了しました。\n\n```json\n"
        '{"done": true, "requirements": {'
        '"summary_ja": "テスト", '
        '"goals": ["g"], '
        '"must_haves": ["m"], '
        '"nice_to_haves": [], '
        '"constraints": [], '
        '"acceptance_criteria": ["a"]}}\n'
        "```"
    )
    done, req = NegotiationAgent._try_extract_done(text)
    assert done is True
    assert req["summary_ja"] == "テスト"
    assert req["goals"] == ["g"]


def test_try_extract_done_handles_nested_json_in_fenced_block():
    """Regression for the non-greedy regex bug."""
    text = (
        '```json\n{"done": true, "requirements": '
        '{"goals": ["g"], "must_haves": ["m"], "nice_to_haves": [], '
        '"constraints": [], "acceptance_criteria": ["a"], "summary_ja": "ok"}}\n```'
    )
    done, req = NegotiationAgent._try_extract_done(text)
    assert done is True
    # The full nested object made it through, not a truncated piece.
    assert req["goals"] == ["g"]
    assert req["acceptance_criteria"] == ["a"]


def test_try_extract_done_requires_requirements_dict():
    text = '```json\n{"done": true, "requirements": "not a dict"}\n```'
    done, req = NegotiationAgent._try_extract_done(text)
    assert done is False


def test_cloud_safe_messages_redacts_user_content_when_redaction_enabled(config):
    from smbagent.cloud_llm_guard import sanitize_cloud_messages

    cfg = type(config)(**{**config.__dict__, "voice_cloud_redaction_enabled": True})
    messages = [{"role": "user", "content": "mail me at a@example.com"}]
    sanitized = sanitize_cloud_messages(cfg, messages)
    assert sanitized[0]["content"] != messages[0]["content"]
    assert "[REDACTED_EMAIL]" in sanitized[0]["content"]

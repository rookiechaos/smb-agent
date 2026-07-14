from __future__ import annotations

from .config import Config
from .voice_hardening import sanitize_transcript_for_cloud


def cloud_redaction_enabled(config: Config) -> bool:
    return bool(config.voice_cloud_redaction_enabled)


def sanitize_cloud_text(config: Config, text: str) -> str:
    if not cloud_redaction_enabled(config):
        return text
    return sanitize_transcript_for_cloud(
        text,
        mode=config.voice_cloud_minimization_mode,
    ).sanitized_text


def sanitize_cloud_messages(config: Config, messages: list[dict[str, str]]) -> list[dict[str, str]]:
    if not cloud_redaction_enabled(config):
        return messages
    sanitized: list[dict[str, str]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "user" and isinstance(content, str):
            sanitized.append({**message, "content": sanitize_cloud_text(config, content)})
        else:
            sanitized.append(message)
    return sanitized


__all__ = [
    "cloud_redaction_enabled",
    "sanitize_cloud_text",
    "sanitize_cloud_messages",
]

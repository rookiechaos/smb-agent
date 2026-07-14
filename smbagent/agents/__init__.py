"""Internal agents — Qualify, Negotiation, Plan, Coding, Validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..config import Config

if TYPE_CHECKING:
    from anthropic import Anthropic


def build_anthropic_client(config: Config) -> Anthropic:
    """Single source of truth for Anthropic client construction.

    Wires the per-call timeout and (optionally) an explicit API key. When the
    key is None, the SDK falls back to env vars and standard auth chains.
    """
    if config.local_only_mode:
        raise RuntimeError(
            "SMBAGENT_LOCAL_ONLY_MODE=true blocks Anthropic-backed agents until "
            "a real local LLM backend is integrated."
        )
    try:
        from anthropic import Anthropic
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "The Anthropic SDK is required for Anthropic-backed agents. "
            "Install the project dependencies before running qualify, negotiation, "
            "plan, bridge, humanize, or runtime skills."
        ) from e

    kwargs: dict = {"timeout": config.anthropic_timeout_s}
    if config.anthropic_api_key:
        kwargs["api_key"] = config.anthropic_api_key
    return Anthropic(**kwargs)

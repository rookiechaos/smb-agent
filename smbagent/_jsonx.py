from __future__ import annotations

import json
import re
from typing import Any


def extract_json(text: str) -> Any:
    """Extract a JSON object/array from arbitrary model output.

    Tries, in order:
      1. Every ```json``` or ``` ``` fenced block (parse each, return first that decodes).
      2. Raw-decode starting from each `{` or `[` in the text.

    Raises ValueError if nothing parses.
    """
    for m in re.finditer(r"```(?:json)?\s*\n?(.*?)\n?```", text, flags=re.DOTALL):
        candidate = m.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch not in "{[":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
            return obj
        except json.JSONDecodeError:
            continue

    raise ValueError("No JSON object found in text")

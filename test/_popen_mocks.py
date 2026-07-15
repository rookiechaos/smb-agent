"""Shared `subprocess.Popen` mocking helpers.

Most tests historically returned `subprocess.CompletedProcess` from a fake
`subprocess.run`. After the agents switched to `Popen + communicate` (for PID
tracking + atexit cleanup), `popen_from_run(fn)` adapts those legacy closures
without rewriting each test by hand.


The coding + validation agents call `subprocess.Popen(...).communicate(timeout=...)`
so they can track the spawned PID and clean up on parent exit. Tests need to
patch `Popen` (not `subprocess.run`) and the helper class must implement just
enough of the Popen interface to satisfy agent code.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from typing import Any

from smbagent.workspace import Workspace


def popen_from_run(fake_run: Callable[..., Any]) -> type:
    """Wrap a fake `subprocess.run(...)` function as a Popen-shaped class.

    Behavior preserved:
      - FileNotFoundError raised by the fake → propagates at Popen() construction.
      - subprocess.TimeoutExpired raised by the fake → deferred to .communicate().
      - Any other exception → deferred to .communicate().
      - Returned CompletedProcess → .returncode + .stdout + .stderr exposed.
    """

    class _Popen:
        def __init__(self, args, **kwargs):
            self.args = args
            self.pid = 99999
            self._raise_in_communicate: BaseException | None = None
            try:
                # We pass the legacy keyword set so the closure can accept them.
                result = fake_run(
                    args,
                    cwd=kwargs.get("cwd"),
                    capture_output=True,
                    text=kwargs.get("text", True),
                    timeout=kwargs.get("timeout"),
                    check=False,
                )
            except FileNotFoundError:
                raise
            except subprocess.TimeoutExpired as e:
                self._raise_in_communicate = e
                self.returncode = -1
                return
            except BaseException as e:  # noqa: BLE001
                self._raise_in_communicate = e
                self.returncode = -1
                return
            self.returncode = result.returncode
            self._stdout = result.stdout or ""
            self._stderr = result.stderr or ""

        def communicate(self, timeout=None):
            if self._raise_in_communicate is not None:
                exc = self._raise_in_communicate
                # Real Popen semantics: after timeout+kill, a second communicate() returns
                # the partial buffers and does NOT re-raise. Clear so the agent's
                # cleanup-communicate() call doesn't crash.
                self._raise_in_communicate = None
                raise exc
            return getattr(self, "_stdout", ""), getattr(self, "_stderr", "")

        def kill(self):
            return None

        def wait(self, timeout=None):
            return self.returncode

    return _Popen


def make_codex_popen(
    workspace: Workspace,
    round_n: int,
    *,
    write_verdict: dict | str | None = None,
    raises: BaseException | type[BaseException] | None = None,
    returncode: int = 0,
    stdout: str = "fake stdout",
    stderr: str = "",
    on_construct: Callable[..., None] | None = None,
) -> type:
    """Build a Popen-mock class for use in tests of ValidationAgent.

    Behavior is parameterized to match the legacy `_fake_codex(...)` helper.

    - `write_verdict=dict` writes that as verdict.json (valid JSON)
    - `write_verdict=str`  writes that string verbatim (lets you simulate bad JSON)
    - `write_verdict=None` does NOT write the file (simulates codex misbehavior)
    - `raises=FileNotFoundError` raises at Popen() construction
    - `raises=subprocess.TimeoutExpired(...)` raises from communicate()
    - `raises=<other>` raises from communicate()
    """

    def _maybe_raise_at_construct():
        if raises is None:
            return
        # FileNotFoundError fires at construction (Popen can't even spawn).
        cls = raises if isinstance(raises, type) else type(raises)
        if cls is FileNotFoundError:
            raise raises if isinstance(raises, BaseException) else FileNotFoundError("codex")

    class _Popen:
        def __init__(self, args, **kwargs):
            _maybe_raise_at_construct()
            self.args = args
            self.pid = 90001
            self.returncode = returncode
            # Side effects after construction (writing verdict.json, custom callback).
            if write_verdict is not None:
                p = workspace.verdict_path(round_n)
                if isinstance(write_verdict, str):
                    p.write_text(write_verdict, encoding="utf-8")
                else:
                    p.write_text(json.dumps(write_verdict), encoding="utf-8")
            if on_construct is not None:
                on_construct(args, **kwargs)

        def communicate(self, timeout=None):
            if raises is not None and not getattr(self, "_raised_once", False):
                cls = raises if isinstance(raises, type) else type(raises)
                if cls is subprocess.TimeoutExpired:
                    self._raised_once = True
                    raise (
                        raises
                        if isinstance(raises, BaseException)
                        else subprocess.TimeoutExpired(self.args, timeout)
                    )
                if cls is not FileNotFoundError:
                    self._raised_once = True
                    # Generic non-construct exception: raise from communicate.
                    raise raises if isinstance(raises, BaseException) else raises()
            return stdout, stderr

        def kill(self):
            return None

        def wait(self, timeout=None):
            return self.returncode

    return _Popen


def make_claude_popen(
    *,
    raises: BaseException | type[BaseException] | None = None,
    returncode: int = 0,
    stdout: str = "claude done",
    stderr: str = "",
    on_construct: Callable[..., None] | None = None,
) -> type:
    """Popen mock for CodingAgent — similar shape, but no verdict-file mechanic."""

    def _maybe_raise_at_construct():
        if raises is None:
            return
        cls = raises if isinstance(raises, type) else type(raises)
        if cls is FileNotFoundError:
            raise raises if isinstance(raises, BaseException) else FileNotFoundError("claude")

    class _Popen:
        def __init__(self, args, **kwargs):
            _maybe_raise_at_construct()
            self.args = args
            self.pid = 80001
            self.returncode = returncode
            if on_construct is not None:
                on_construct(args, **kwargs)

        def communicate(self, timeout=None):
            if raises is not None:
                cls = raises if isinstance(raises, type) else type(raises)
                if cls is subprocess.TimeoutExpired:
                    raise (
                        raises
                        if isinstance(raises, BaseException)
                        else subprocess.TimeoutExpired(self.args, timeout)
                    )
                if cls is not FileNotFoundError:
                    raise raises if isinstance(raises, BaseException) else raises()
            return stdout, stderr

        def kill(self):
            return None

        def wait(self, timeout=None):
            return self.returncode

    return _Popen

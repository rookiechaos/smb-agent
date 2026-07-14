from __future__ import annotations

from pathlib import Path

from .workspace import Workspace


def publish_workspace_artifact_freshness(
    workspace: Workspace,
    *,
    artifact_key: str,
    artifact_paths: list[str],
    writer: str,
    status: str = "fresh",
    detail: str = "",
    source_sections: list[str] | None = None,
) -> dict:
    """Publish reducer-backed freshness metadata for a derived workspace artifact.

    The artifact itself remains a direct write. This helper only publishes a
    freshness/status record into public workspace state so maintainers can tell
    whether the visible artifact is current.
    """
    store = workspace._state_store()
    current = store.read()
    source_revision = int(current.get("revision") or 0)
    return store.reduce_update(
        section="artifact_freshness",
        patch={
            artifact_key: {
                "status": status,
                "detail": detail,
                "artifact_paths": list(artifact_paths),
                "source_revision": source_revision,
                "source_sections": list(source_sections or []),
            }
        },
        writer=writer,
    )


def artifact_path_strings(paths: list[Path], *, relative_to: Path) -> list[str]:
    out: list[str] = []
    for path in paths:
        try:
            out.append(str(path.relative_to(relative_to)))
        except ValueError:
            out.append(str(path))
    return out

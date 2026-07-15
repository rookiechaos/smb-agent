from __future__ import annotations

from dataclasses import replace

import pytest

from smbagent.iteration_tuning import (
    IterationTuning,
    IterationTuningPatch,
    apply_patch,
    customer_tuning_path,
    delete_customer_iteration_tuning,
    describe_iteration_tuning,
    global_tuning_path,
    load_iteration_tuning,
    read_tuning_changes,
    record_tuning_change,
    save_customer_iteration_tuning,
    save_global_iteration_tuning,
    tuning_change_log_path,
)
from smbagent.workspace import Workspace


def test_env_defaults_match_config(config):
    t = IterationTuning.from_config(config)
    assert t.anneal_temp_creative == 0.7
    assert t.bridge_orchestrator_enabled is False  # conftest


def test_global_file_overrides_env(config, tmp_path):
    cfg = replace(config, root=tmp_path)
    save_global_iteration_tuning(
        cfg,
        IterationTuning.from_config(cfg).model_copy(
            update={"anneal_temp_creative": 0.55, "notes": "pioneer feedback"},
        ),
    )
    effective = load_iteration_tuning(cfg)
    assert effective.anneal_temp_creative == 0.55
    assert "pioneer" in effective.notes


def test_customer_overrides_global(config, workspace: Workspace, tmp_path):
    cfg = replace(config, root=tmp_path, workspaces_dir=workspace.path.parent)
    save_global_iteration_tuning(
        cfg,
        IterationTuning.from_config(cfg).model_copy(
            update={"anneal_temp_creative": 0.6},
        ),
    )
    save_customer_iteration_tuning(
        workspace,
        IterationTuning.from_config(cfg).model_copy(
            update={"anneal_temp_creative": 0.45, "notes": "this customer stalls"},
        ),
    )
    effective = load_iteration_tuning(cfg, workspace.customer_id)
    assert effective.anneal_temp_creative == 0.45


def test_patch_partial_update(config):
    base = IterationTuning.from_config(config)
    patched = apply_patch(
        base,
        IterationTuningPatch(anneal_temp_final=0.1, notes="tighter finale"),
    )
    assert patched.anneal_temp_final == 0.1
    assert patched.anneal_temp_creative == base.anneal_temp_creative


def test_describe_shows_layers(config, workspace: Workspace, tmp_path):
    cfg = replace(config, root=tmp_path, workspaces_dir=workspace.path.parent)
    save_global_iteration_tuning(
        cfg,
        IterationTuning.from_config(cfg).model_copy(update={"anneal_stale_rounds": 3}),
    )
    view = describe_iteration_tuning(cfg, workspace.customer_id)
    assert view.effective.anneal_stale_rounds == 3
    assert view.global_override is not None


def test_delete_customer_override(config, workspace: Workspace, tmp_path):
    cfg = replace(config, root=tmp_path, workspaces_dir=workspace.path.parent)
    save_customer_iteration_tuning(
        workspace,
        IterationTuning.from_config(cfg).model_copy(update={"anneal_temp_creative": 0.2}),
    )
    assert customer_tuning_path(workspace).exists()
    delete_customer_iteration_tuning(workspace)
    assert not customer_tuning_path(workspace).exists()
    assert load_iteration_tuning(cfg, workspace.customer_id).anneal_temp_creative == 0.7


def test_invalid_global_json_raises(config, tmp_path):
    cfg = replace(config, root=tmp_path)
    path = global_tuning_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_iteration_tuning(cfg)


def test_to_annealing_temps(config):
    t = IterationTuning.from_config(config)
    temps = t.to_annealing_temps()
    assert temps.creative == t.anneal_temp_creative


def test_record_tuning_change_writes_audit_log(config, tmp_path):
    cfg = replace(config, root=tmp_path)
    before = IterationTuning.from_config(cfg)
    after = before.model_copy(update={"anneal_temp_creative": 0.5, "notes": "remote tune"})

    path = record_tuning_change(
        cfg,
        action="set",
        scope="global",
        customer_id=None,
        operator="alice@example.com",
        notes="raise completion rate",
        target_path=global_tuning_path(cfg),
        before=before,
        after=after,
    )

    assert path == tuning_change_log_path(cfg)
    rows = read_tuning_changes(cfg)
    assert len(rows) == 1
    assert rows[0].operator == "human:alice@example.com"
    assert rows[0].after["anneal_temp_creative"] == 0.5


def test_read_tuning_changes_filters_by_customer(config, workspace: Workspace, tmp_path):
    cfg = replace(config, root=tmp_path, workspaces_dir=workspace.path.parent)
    before = IterationTuning.from_config(cfg)
    after = before.model_copy(update={"anneal_temp_final": 0.1})
    record_tuning_change(
        cfg,
        action="set",
        scope="customer",
        customer_id=workspace.customer_id,
        operator="human:bob",
        notes="customer-specific tune",
        target_path=customer_tuning_path(workspace),
        before=before,
        after=after,
    )
    record_tuning_change(
        cfg,
        action="set",
        scope="customer",
        customer_id="other-customer",
        operator="human:carol",
        notes="other",
        target_path=tmp_path / "other.json",
        before=before,
        after=after,
    )

    rows = read_tuning_changes(cfg, customer_id=workspace.customer_id)
    assert len(rows) == 1
    assert rows[0].customer_id == workspace.customer_id

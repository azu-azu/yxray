from __future__ import annotations

import json
import pathlib
from datetime import datetime

import pytest

from yxray.manual_clusters import (
    backup_cluster_file,
    list_cluster_backups,
    load_manual_cluster_config,
    restore_cluster_backup,
    workflow_fingerprint,
)
from yxray.models.types import AnchorName, ToolID
from yxray.models.workflow import AlteryxConnection, AlteryxNode, WorkflowDoc


def _doc() -> WorkflowDoc:
    return WorkflowDoc(
        filepath="fixture.yxmd",
        nodes=(
            AlteryxNode(tool_id=ToolID(1), tool_type="InputData", x=0, y=0),
            AlteryxNode(tool_id=ToolID(2), tool_type="Filter", x=10, y=0),
            AlteryxNode(tool_id=ToolID(3), tool_type="Select", x=20, y=0),
        ),
        connections=(
            AlteryxConnection(
                src_tool=ToolID(1),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(2),
                dst_anchor=AnchorName("Input"),
            ),
            AlteryxConnection(
                src_tool=ToolID(2),
                src_anchor=AnchorName("Output"),
                dst_tool=ToolID(3),
                dst_anchor=AnchorName("Input"),
            ),
        ),
    )


def _write_config(path: pathlib.Path, doc: WorkflowDoc, clusters: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "workflow_fingerprint": workflow_fingerprint(doc),
                "manual_clusters": clusters,
            }
        ),
        encoding="utf-8",
    )


def test_load_manual_cluster_config_normalizes_valid_file(
    tmp_path: pathlib.Path,
) -> None:
    doc = _doc()
    path = tmp_path / "clusters.json"
    _write_config(path, doc, [{"label": "prep", "tool_ids": [3, 1]}])

    config = load_manual_cluster_config(path, doc)

    assert config == {
        "schema_version": 1,
        "workflow_fingerprint": workflow_fingerprint(doc),
        "manual_clusters": [{"label": "prep", "tool_ids": [1, 3]}],
    }


def test_load_manual_cluster_config_rejects_fingerprint_mismatch(
    tmp_path: pathlib.Path,
) -> None:
    doc = _doc()
    path = tmp_path / "clusters.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "workflow_fingerprint": "wrong",
                "manual_clusters": [{"label": "prep", "tool_ids": [1, 2]}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="does not match"):
        load_manual_cluster_config(path, doc)


def test_load_manual_cluster_config_rejects_duplicate_membership(
    tmp_path: pathlib.Path,
) -> None:
    doc = _doc()
    path = tmp_path / "clusters.json"
    _write_config(
        path,
        doc,
        [
            {"label": "a", "tool_ids": [1, 2]},
            {"label": "b", "tool_ids": [2, 3]},
        ],
    )

    with pytest.raises(ValueError, match="multiple manual clusters"):
        load_manual_cluster_config(path, doc)


def test_backup_and_restore_cluster_file(tmp_path: pathlib.Path) -> None:
    cluster_file = tmp_path / "clusters.json"
    cluster_file.write_text('{"version": 1}', encoding="utf-8")
    now = datetime(2026, 7, 5, 15, 30, 12)

    backup = backup_cluster_file(
        cluster_file,
        now=now,
    )
    cluster_file.write_text('{"version": 2}', encoding="utf-8")
    second_backup = backup_cluster_file(
        cluster_file,
        now=now,
    )
    cluster_file.write_text('{"version": 3}', encoding="utf-8")
    restore_now = datetime(2026, 7, 5, 16, 0, 0)
    restored_from = restore_cluster_backup(cluster_file, now=restore_now)
    restore_safety_backup = (
        tmp_path / "clusters.backups" / "clusters_20260705_160000.json"
    )

    assert backup == tmp_path / "clusters.backups" / "clusters_20260705_153012.json"
    assert second_backup == (
        tmp_path / "clusters.backups" / "clusters_20260705_153012_2.json"
    )
    assert restored_from == second_backup
    assert cluster_file.read_text(encoding="utf-8") == '{"version": 2}'
    assert restore_safety_backup.read_text(encoding="utf-8") == '{"version": 3}'
    assert list_cluster_backups(cluster_file) == [
        restore_safety_backup,
        second_backup,
        backup,
    ]

"""Manual cluster config loading and validation for inspect reports."""

from __future__ import annotations

import json
import pathlib
import shutil
from datetime import datetime
from typing import Any

from yxray.models.workflow import WorkflowDoc

SCHEMA_VERSION = 1
BACKUP_DIR_SUFFIX = ".backups"


def workflow_fingerprint(doc: WorkflowDoc) -> str:
    """Return the same lightweight fingerprint used by single_graph.js."""
    data_nodes = [n for n in doc.nodes if "ToolContainer" not in n.tool_type]
    data_node_ids = {int(n.tool_id) for n in data_nodes}

    parts: list[str] = []
    for node in sorted(data_nodes, key=lambda n: int(n.tool_id)):
        parts.append(f"n:{int(node.tool_id)}:{node.tool_type}")
    for conn in sorted(
        (
            c
            for c in doc.connections
            if int(c.src_tool) in data_node_ids and int(c.dst_tool) in data_node_ids
        ),
        key=lambda c: (int(c.src_tool), int(c.dst_tool)),
    ):
        parts.append(f"e:{int(conn.src_tool)}>{int(conn.dst_tool)}")
    return _fnv1a_32("|".join(parts))


def load_manual_cluster_config(
    path: pathlib.Path, doc: WorkflowDoc
) -> dict[str, Any]:
    """Load a manual cluster JSON file and validate it against a workflow."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid cluster JSON: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Cannot read cluster file: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("Cluster config must be a JSON object")
    if raw.get("schema_version") != SCHEMA_VERSION:
        version = raw.get("schema_version")
        raise ValueError(f"Unsupported cluster schema_version: {version}")

    expected_fingerprint = workflow_fingerprint(doc)
    if raw.get("workflow_fingerprint") != expected_fingerprint:
        raise ValueError("Cluster config does not match this workflow")

    clusters = raw.get("manual_clusters")
    if not isinstance(clusters, list):
        raise ValueError("manual_clusters must be a list")

    nodes_by_id = {
        int(node.tool_id): node
        for node in doc.nodes
        if "ToolContainer" not in node.tool_type
    }
    used_ids: set[int] = set()
    normalized_clusters: list[dict[str, Any]] = []

    for index, cluster in enumerate(clusters, start=1):
        if not isinstance(cluster, dict):
            raise ValueError(f"manual_clusters[{index}] must be an object")
        label = str(cluster.get("label", "")).strip()
        if not label:
            raise ValueError(f"manual_clusters[{index}].label is required")
        raw_tool_ids = cluster.get("tool_ids")
        if not isinstance(raw_tool_ids, list):
            raise ValueError(f"manual_clusters[{index}].tool_ids must be a list")

        local_ids: set[int] = set()
        tool_ids: list[int] = []
        for raw_id in raw_tool_ids:
            if not isinstance(raw_id, int):
                raise ValueError(
                    f"manual_clusters[{index}] contains a non-integer ToolID"
                )
            node = nodes_by_id.get(raw_id)
            if node is None:
                raise ValueError(
                    f"manual_clusters[{index}] contains unknown ToolID {raw_id}"
                )
            if node.container_id is not None:
                raise ValueError(
                    f"manual_clusters[{index}] contains ToolID {raw_id} "
                    "inside a ToolContainer"
                )
            if raw_id in local_ids:
                raise ValueError(
                    f"manual_clusters[{index}] contains duplicate ToolID {raw_id}"
                )
            if raw_id in used_ids:
                raise ValueError(f"ToolID {raw_id} appears in multiple manual clusters")
            local_ids.add(raw_id)
            tool_ids.append(raw_id)

        if len(tool_ids) < 2:
            raise ValueError(
                f"manual_clusters[{index}] must contain at least 2 ToolIDs"
            )
        used_ids.update(tool_ids)
        normalized_clusters.append({"label": label, "tool_ids": sorted(tool_ids)})

    return {
        "schema_version": SCHEMA_VERSION,
        "workflow_fingerprint": expected_fingerprint,
        "manual_clusters": normalized_clusters,
    }


def backup_cluster_file(
    cluster_file: pathlib.Path, *, now: datetime | None = None
) -> pathlib.Path:
    """Copy a cluster JSON file into a timestamped sibling backup directory."""
    if not cluster_file.is_file():
        raise ValueError(f"Cluster file not found: {cluster_file}")
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    backup_dir = _backup_dir(cluster_file)
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = _next_backup_path(
        backup_dir,
        stem=cluster_file.stem,
        suffix=cluster_file.suffix,
        timestamp=timestamp,
    )
    shutil.copy2(cluster_file, backup_path)
    return backup_path


def list_cluster_backups(cluster_file: pathlib.Path) -> list[pathlib.Path]:
    """Return backups for a cluster file, newest first."""
    backup_dir = _backup_dir(cluster_file)
    if not backup_dir.is_dir():
        return []
    pattern = f"{cluster_file.stem}_*{cluster_file.suffix}"
    return sorted(backup_dir.glob(pattern), reverse=True)


def restore_cluster_backup(
    cluster_file: pathlib.Path, backup_file: pathlib.Path | None = None
) -> pathlib.Path:
    """Restore a backup into the cluster file path and return the restored backup."""
    selected_backup = backup_file
    if selected_backup is None:
        backups = list_cluster_backups(cluster_file)
        if not backups:
            raise ValueError(f"No backups found for {cluster_file}")
        selected_backup = backups[0]
    if not selected_backup.is_file():
        raise ValueError(f"Backup file not found: {selected_backup}")
    cluster_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(selected_backup, cluster_file)
    return selected_backup


def _fnv1a_32(text: str) -> str:
    hash_value = 2166136261
    for char in text:
        hash_value ^= ord(char)
        hash_value = (hash_value * 16777619) & 0xFFFFFFFF
    return f"{hash_value:x}"


def _backup_dir(cluster_file: pathlib.Path) -> pathlib.Path:
    return cluster_file.parent / f"{cluster_file.stem}{BACKUP_DIR_SUFFIX}"


def _next_backup_path(
    backup_dir: pathlib.Path, *, stem: str, suffix: str, timestamp: str
) -> pathlib.Path:
    first = backup_dir / f"{stem}_{timestamp}{suffix}"
    if not first.exists():
        return first

    counter = 2
    while True:
        candidate = backup_dir / f"{stem}_{timestamp}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1

"""Normalization pipeline entry point.

Pure function: normalize(WorkflowDoc) -> NormalizedWorkflowDoc.
No I/O, no side effects, no CLI knowledge, no mutable state.

Pipeline order per node: strip_noise(config) -> json.dumps(sort_keys=True) -> sha256()

C14N canonicalization is implemented as canonical dict serialization:
json.dumps with sort_keys=True achieves attribute-order independence at every
nesting level. This is correct because the Phase 2 parser already converted
<Properties> XML into Python dicts using the @key/#text convention — lxml's
etree.canonicalize() operates on XML element objects, not dicts.

Position separation:
  NormalizedNode.position = (node.x, node.y) from source AlteryxNode.
  node.x and node.y are NEVER included in the config dict passed to hashing.
  The two data paths (config_hash and position) are structurally separate.
  The --include-positions flag is a Phase 5 (differ) and Phase 9 (CLI) concern;
  normalize() is flag-agnostic.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from alteryx_git_companion.models.normalized import (
    NormalizedNode,
    NormalizedWorkflowDoc,
)
from alteryx_git_companion.models.types import ConfigHash
from alteryx_git_companion.models.workflow import AlteryxNode, WorkflowDoc
from alteryx_git_companion.normalizer._strip import strip_noise


def normalize(workflow_doc: WorkflowDoc) -> NormalizedWorkflowDoc:
    """Pure transformation: WorkflowDoc -> NormalizedWorkflowDoc.

    Each node's config dict is stripped of Alteryx noise, canonicalized via
    json.dumps(sort_keys=True), and SHA-256 hashed to produce config_hash.
    Position (x, y) is carried forward separately and never included in the hash.

    Returns a NormalizedWorkflowDoc with:
      - .nodes: tuple[NormalizedNode, ...] — one per source node, in source order
      - .connections: preserved unchanged from source WorkflowDoc
      - .source: original WorkflowDoc for downstream metadata access
    """
    normalized_nodes = tuple(_normalize_node(node) for node in workflow_doc.nodes)
    return NormalizedWorkflowDoc(
        source=workflow_doc,
        nodes=normalized_nodes,
        connections=workflow_doc.connections,
    )


def _normalize_node(node: AlteryxNode) -> NormalizedNode:
    """Strip, canonicalize, and hash a single node's config dict."""
    stripped = strip_noise(node.config)
    config_hash = ConfigHash(_compute_config_hash(stripped))
    return NormalizedNode(
        source=node,
        config_hash=config_hash,
        position=(node.x, node.y),
    )


def _compute_config_hash(stripped_config: dict[str, Any]) -> str:
    """SHA-256 hex digest of canonical config bytes.

    Canonical form: json.dumps with sort_keys=True (attribute-order independence
    at every nesting level) and compact separators (no whitespace differences).
    ensure_ascii=False preserves Unicode without percent-encoding noise.

    Returns a 64-character lowercase hexadecimal string.
    """
    canonical_bytes = json.dumps(
        stripped_config,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,  # safety net: non-JSON-serializable types become strings
    ).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()

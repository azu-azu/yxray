from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from alteryx_git_companion.models import AlteryxNode, DiffResult, EdgeDiff, NodeDiff


class JSONRenderer:
    """Serialize a DiffResult to a JSON string matching the ACD diff schema.

    Schema (no separate schema file per CONTEXT.md decisions):

    {
      "summary": {
        "added": <int>,       # count of added tools
        "removed": <int>,     # count of removed tools
        "modified": <int>,    # count of modified tools
        "connections": <int>  # count of connection changes (== len(connections array))
      },
      "tools": [
        {
          "tool_name": <str>,    # tool_type from AlteryxNode
                              #   e.g. "AlteryxBasePluginsGui.Filter"
          "changes": [
            {
              "id": <int>,            # ToolID cast to int
              "display_name": <str>,  # tool_type (same as tool_name)
              "change_type": <str>    # "added" | "removed" | "modified"
            }
          ]
        }
      ],
      "connections": [
        {
          "src_tool": <int>,    # ToolID cast to int
          "src_anchor": <str>,  # AnchorName cast to str
          "dst_tool": <int>,    # ToolID cast to int
          "dst_anchor": <str>,  # AnchorName cast to str
          "change_type": <str>  # "added" | "removed"
        }
      ]
    }

    Tools are sorted alphabetically by tool_name for deterministic output.
    summary.connections always equals len(connections array).
    """

    def render(self, result: DiffResult) -> str:
        """Serialize result to a JSON string. Returns valid, human-readable JSON."""
        payload = self._build_payload(result)
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def _build_payload(self, result: DiffResult) -> dict[str, Any]:
        connections = [self._edge_to_dict(e) for e in result.edge_diffs]
        summary = {
            "added": len(result.added_nodes),
            "removed": len(result.removed_nodes),
            "modified": len(result.modified_nodes),
            "connections": len(connections),  # invariant: == len(connections array)
        }
        tools = self._build_tools(result)
        return {"summary": summary, "tools": tools, "connections": connections}

    def _build_tools(self, result: DiffResult) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for node in result.added_nodes:
            groups[node.tool_type].append(self._node_to_change(node, "added"))
        for node in result.removed_nodes:
            groups[node.tool_type].append(self._node_to_change(node, "removed"))
        for nd in result.modified_nodes:
            # Use old_node.tool_type as the identity anchor for modified nodes
            groups[nd.old_node.tool_type].append(self._node_diff_to_change(nd))

        return [
            {"tool_name": tool_type, "changes": changes}
            for tool_type, changes in sorted(groups.items())
        ]

    def _node_to_change(self, node: AlteryxNode, change_type: str) -> dict[str, Any]:
        return {
            "id": int(node.tool_id),  # explicit cast: ToolID is NewType(int)
            "display_name": node.tool_type,
            "change_type": change_type,
        }

    def _node_diff_to_change(self, nd: NodeDiff) -> dict[str, Any]:
        return {
            "id": int(nd.tool_id),  # explicit cast: ToolID is NewType(int)
            "display_name": nd.old_node.tool_type,
            "change_type": "modified",
        }

    def _edge_to_dict(self, edge: EdgeDiff) -> dict[str, Any]:
        return {
            "src_tool": int(edge.src_tool),  # explicit cast: ToolID is NewType(int)
            "src_anchor": str(
                edge.src_anchor
            ),  # explicit cast: AnchorName is NewType(str)
            "dst_tool": int(edge.dst_tool),
            "dst_anchor": str(edge.dst_anchor),
            "change_type": edge.change_type,
        }

"""Renderer stage for alteryx_git_companion.

Public surface: JSONRenderer, HTMLRenderer, GraphRenderer

  from alteryx_git_companion.renderers import JSONRenderer, HTMLRenderer, GraphRenderer
  graph_renderer = GraphRenderer()
  graph_html = graph_renderer.render(result, all_connections, nodes_old, nodes_new)
  html_renderer = HTMLRenderer()
  html = html_renderer.render(result, graph_html=graph_html)
"""

from __future__ import annotations

from alteryx_git_companion.renderers.graph_renderer import GraphRenderer
from alteryx_git_companion.renderers.html_renderer import HTMLRenderer
from alteryx_git_companion.renderers.json_renderer import JSONRenderer

__all__ = ["JSONRenderer", "HTMLRenderer", "GraphRenderer"]

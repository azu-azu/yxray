"""Renderer stage for yxray.

Public surface: JSONRenderer, HTMLRenderer, GraphRenderer, SingleGraphRenderer,
InspectReportRenderer

  from yxray.renderers import JSONRenderer, HTMLRenderer, GraphRenderer
  graph_renderer = GraphRenderer()
  graph_html = graph_renderer.render(result, all_connections, nodes_old, nodes_new)
  html_renderer = HTMLRenderer()
  html = html_renderer.render(result, graph_html=graph_html)
"""

from __future__ import annotations

from yxray.renderers.graph_renderer import GraphRenderer
from yxray.renderers.html_renderer import HTMLRenderer
from yxray.renderers.inspect_report_renderer import InspectReportRenderer
from yxray.renderers.json_renderer import JSONRenderer
from yxray.renderers.single_graph_renderer import SingleGraphRenderer

__all__ = ["JSONRenderer", "HTMLRenderer", "GraphRenderer", "SingleGraphRenderer", "InspectReportRenderer"]

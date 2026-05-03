"""Domain-specific subgraphs — compiled into the main graph."""

from nuzantara_graph.subgraphs.company import make_company_subgraph
from nuzantara_graph.subgraphs.visa import make_visa_subgraph
from nuzantara_graph.subgraphs.property import make_property_subgraph
from nuzantara_graph.subgraphs.tax import make_tax_subgraph

__all__ = [
    "make_company_subgraph",
    "make_visa_subgraph",
    "make_property_subgraph",
    "make_tax_subgraph",
]

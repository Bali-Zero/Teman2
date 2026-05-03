"""Curiosity Loop — autonomous KG gap detection, research, and proposal pipeline.

# Organo: graph-engine/curiosity → produce kg_proposals → consuma gap_detector.GapResult

SYMBIOSIS Pilastro 6: "La curiosità guidata da gap su knowledge graph
non è stata studiata da nessuno. Stiamo inventando."

Pipeline: scan gaps → prioritize → classify tier → dispatch research →
          validate (Self-RAG) → propose (NEVER direct KG write) → Zero approves

Legge 5 enforced: proposals MUST be approved by Zero before applying to
kg_nodes/kg_edges. The propose-only invariant is the sacred safety gate.
"""

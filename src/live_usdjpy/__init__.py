"""USD/JPY forward (shadow) monitoring system. MONITORING SIDE ONLY: reads current 2026 data, never research data
paths for evaluation; research code must never import this package (enforced by tests/test_live_usdjpy_registry.py).
No broker, no orders, no LLM in any decision path."""

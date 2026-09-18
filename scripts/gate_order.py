"""Single source of the v2 gate order.

This tuple used to be mirrored in ``harness.py``, ``harness_status.py``,
``qa/check_gates.py`` and ``mcp_tools/state.py``; any new gate or reorder had
to be applied four times or the surfaces drifted.  Import it from here — the
other modules re-export the same tuple so existing references keep working.
"""

GATE_ORDER = ("m1", "p1", "p2", "w1", "w2", "s1")

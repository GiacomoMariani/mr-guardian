# Python Best Practices for MR Guardian

## PYTHON-PRINT-001 — Prefer logging over print calls

Production Python code should avoid newly introduced `print(...)` calls.

Use structured logging so output can be routed, filtered, and tested consistently.

"""LLM components: matcher, risk, judge, composer, extractor.

All calls go through ``client.py`` (JSON mode, retries, cost capture). Prompts
live as versioned markdown under ``prompts/`` so every change is a reviewable
diff. The brain is added on top of the walking skeleton — see PLAN.md v1.5.
"""

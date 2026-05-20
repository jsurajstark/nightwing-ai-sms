"""Serialize LLM extraction so only one intake runs Ollama at a time."""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

_llm_lock = threading.Lock()


def llm_extraction_lock() -> threading.Lock:
    """Process-wide lock: one intake may call the LLM at a time."""
    return _llm_lock

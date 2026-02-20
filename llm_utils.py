"""
LLM utilities for Gomas Legal Engine.
- Model: claude-3-5-haiku-20241022
- In-memory cache for repeated prompts
- Exponential-backoff retry on transient errors
- PageIndex adapter (Anthropic instead of OpenAI)
"""
from __future__ import annotations

import asyncio
import hashlib
from typing import Optional

import anthropic
from loguru import logger

import config

# ─── Client (shared, lazy-initialized) ───────────────────────────────────────
_client: Optional[anthropic.AsyncAnthropic] = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


# ─── Key validation ───────────────────────────────────────────────────────────

def is_valid_key(key: str = "") -> bool:
    k = key or config.ANTHROPIC_API_KEY
    return bool(k and k.startswith("sk-"))


# ─── Token counting ───────────────────────────────────────────────────────────

def count_tokens(text: str, model: str = "") -> int:
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text) // 4


# ─── Prompt cache (simple in-memory, keyed by hash of first 400 chars) ────────
_CACHE: dict[str, str] = {}
_CACHE_MAX = 256


def _cache_key(prompt: str) -> str:
    return hashlib.md5(prompt[:400].encode()).hexdigest()


def _get_cached(prompt: str) -> Optional[str]:
    return _CACHE.get(_cache_key(prompt))


def _set_cached(prompt: str, result: str):
    key = _cache_key(prompt)
    if len(_CACHE) >= _CACHE_MAX:
        # Evict oldest entry
        oldest = next(iter(_CACHE))
        del _CACHE[oldest]
    _CACHE[key] = result


# ─── Core completion with retry ───────────────────────────────────────────────

async def generate_completion(
    prompt: str,
    model: str = "",
    max_tokens: int = 0,
    use_cache: bool = False,
) -> str:
    """
    Generates a completion from Claude with exponential-backoff retry.
    Falls back to an empty string on persistent failure.
    """
    if not is_valid_key():
        logger.warning("No valid ANTHROPIC_API_KEY — skipping LLM call.")
        return ""

    if use_cache:
        cached = _get_cached(prompt)
        if cached is not None:
            return cached

    _model     = model or config.LLM_MODEL
    _max_tokens = max_tokens or config.LLM_MAX_TOKENS
    client     = _get_client()

    for attempt in range(config.MAX_RETRIES):
        try:
            msg = await client.messages.create(
                model=_model,
                max_tokens=_max_tokens,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            result = msg.content[0].text
            if use_cache:
                _set_cached(prompt, result)
            return result

        except anthropic.RateLimitError as exc:
            wait = 2 ** attempt
            logger.warning(f"Rate limit hit (attempt {attempt+1}). Retrying in {wait}s…")
            await asyncio.sleep(wait)

        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                wait = 2 ** attempt
                logger.warning(f"Anthropic 5xx error (attempt {attempt+1}). Retrying in {wait}s…")
                await asyncio.sleep(wait)
            else:
                logger.error(f"Anthropic API error {exc.status_code}: {exc.message}")
                return ""

        except Exception as exc:
            logger.error(f"Unexpected LLM error: {exc}")
            return ""

    logger.error(f"All {config.MAX_RETRIES} LLM attempts failed.")
    return ""


# ─── Specialized helpers ──────────────────────────────────────────────────────

async def clean_text_with_llm(text: str) -> str:
    """Uses Claude to fix OCR text without summarizing."""
    prompt = (
        "You are a legal document assistant. Clean and correct the following OCR text.\n"
        "Fix broken words, split concatenated words, correct obvious OCR typos.\n"
        "Do NOT summarize. Return ONLY the full cleaned text.\n\n"
        f"TEXT:\n{text}"
    )
    result = await generate_completion(prompt, max_tokens=4096)
    return result or text  # fall back to original if LLM unavailable


# ─── PageIndex adapter (replaces OpenAI calls inside PageIndex) ───────────────

async def PageIndex_LLM_Adapter(model: str, prompt: str, api_key: str = "") -> str:
    """
    Drop-in replacement for pageindex.utils.ChatGPT_API_async.
    Maps any OpenAI/GPT model name → claude-3-5-haiku-20241022.
    Results are cached to avoid redundant calls during indexing.
    """
    anthropic_model = config.LLM_MODEL
    if "claude" in model:
        anthropic_model = model  # trust explicit Claude model names

    return await generate_completion(prompt, model=anthropic_model, use_cache=True)

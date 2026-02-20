"""
Rule-based document classifier with:
- Hot-reload: re-reads rules.yaml if the file has changed since last load
- Entity extraction integrated (via entity_extractor module)
- Returns type, confidence, tags, entities, requires_review
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

import yaml
from loguru import logger

import config
import entity_extractor as ee

RULES_PATH = config.RULES_PATH


class DocumentClassifier:
    """
    Classifies legal documents by scoring text against YAML-defined rules.
    Supports hot-reload: rules are reloaded automatically when rules.yaml changes.
    """

    def __init__(self):
        self._rules: List[Dict] = []
        self._rules_mtime: float = 0.0
        self._load_rules()

    # ─── Rules loading (hot-reload) ───────────────────────────────────────────

    def _load_rules(self):
        if not os.path.exists(RULES_PATH):
            logger.warning(f"Rules file not found: {RULES_PATH}")
            self._rules = []
            return
        try:
            mtime = os.path.getmtime(RULES_PATH)
            with open(RULES_PATH, "r", encoding="utf-8") as f:
                self._rules = yaml.safe_load(f) or []
            self._rules_mtime = mtime
            logger.debug(f"Loaded {len(self._rules)} classification rules.")
        except Exception as exc:
            logger.error(f"Failed to load rules: {exc}")
            self._rules = []

    def _maybe_reload(self):
        """Reload rules if the YAML file has been modified since last load."""
        try:
            mtime = os.path.getmtime(RULES_PATH)
            if mtime > self._rules_mtime:
                logger.info("rules.yaml changed — hot-reloading…")
                self._load_rules()
        except OSError:
            pass

    # ─── Classification ───────────────────────────────────────────────────────

    def classify(self, text: str) -> Tuple[str, float, List[str]]:
        """
        Scores text against all rules.
        Returns (document_type, confidence_score, tags).
        """
        self._maybe_reload()

        text_lower = text.lower()
        lines = text_lower.split("\n")
        total = len(lines)

        header_region      = "\n".join(lines[: min(50, total)])
        footer_region      = "\n".join(lines[max(0, total - 50):])
        first_pages_region = "\n".join(lines[: min(300, total)])

        best_type  = "sin_clasificar"
        best_score = 0.0
        best_tags: List[str] = []

        for rule in self._rules:
            score = 0.0
            for signal in rule.get("señales_fuertes", []):
                pattern  = signal["texto"].lower()
                location = signal.get("ubicacion", "cualquiera")
                weight   = signal.get("peso", 0.1)

                found = False
                if location in ("encabezado", "inicio"):
                    found = pattern in header_region
                elif location in ("ultimas_2_paginas", "cierre"):
                    found = pattern in footer_region
                elif location.startswith("primeras_"):
                    found = pattern in first_pages_region
                else:
                    found = pattern in text_lower

                if found:
                    score += weight

            score = min(score, 1.0)

            if score > best_score:
                best_score = score
                best_type  = rule["tipo"]
                best_tags  = rule.get("etiquetas", [])

        return best_type, best_score, best_tags

    # ─── Threshold check ─────────────────────────────────────────────────────

    def _requires_review(self, doc_type: str, confidence: float) -> bool:
        if doc_type == "sin_clasificar":
            return True
        for rule in self._rules:
            if rule["tipo"] == doc_type:
                threshold = rule.get("umbral_confianza_alta", 0.7)
                return confidence < threshold
        return confidence < 0.7


# ─── Module-level singleton ───────────────────────────────────────────────────
_CLASSIFIER = DocumentClassifier()


def classify_document(text: str) -> Dict[str, Any]:
    """
    Full classification pipeline — also extracts entities.
    Returns dict with: tipo, confianza, etiquetas, requiere_revision, entidades
    """
    doc_type, confidence, tags = _CLASSIFIER.classify(text)
    requires_review = _CLASSIFIER._requires_review(doc_type, confidence)

    # Entity extraction (safe — never raises)
    try:
        entidades = ee.extract_entities(text)
    except Exception as exc:
        logger.warning(f"Entity extraction failed: {exc}")
        entidades = {}

    return {
        "tipo":              doc_type,
        "confianza":         confidence,
        "etiquetas":         tags,
        "requiere_revision": requires_review,
        "entidades":         entidades,
    }

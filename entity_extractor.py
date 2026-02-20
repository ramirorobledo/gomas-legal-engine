"""
Entity extractor for Mexican legal documents.
Uses spaCy (es_core_news_sm) for NER + curated regex patterns.
"""
from __future__ import annotations

import re
from typing import Dict, List, Any
from loguru import logger

# ─── spaCy (optional — graceful degradation if model not installed) ───────────
try:
    import spacy
    _nlp = spacy.load("es_core_news_sm")
    _SPACY_OK = True
except Exception:
    _nlp = None
    _SPACY_OK = False
    logger.warning(
        "spaCy model 'es_core_news_sm' not available. "
        "Run: python -m spacy download es_core_news_sm\n"
        "Entity extraction will use regex only."
    )


# ─── Regex patterns ───────────────────────────────────────────────────────────

# Número de expediente / toca
_RE_EXPEDIENTE = re.compile(
    r"(?:expediente|toca|causa|juicio|amparo)\s*(?:número|num\.?|no\.?)?\s*"
    r"([\w\-/]+/\d{4}(?:/[A-Z0-9\-]+)?)",
    re.IGNORECASE,
)

# Número de folio / registro
_RE_FOLIO = re.compile(
    r"(?:folio|registro)\s*(?:número|num\.?|no\.?)?\s*([A-Z0-9\-/]+)",
    re.IGNORECASE,
)

# Fechas en español (e.g. "12 de enero de 2024", "12/01/2024")
_RE_FECHA = re.compile(
    r"\b(\d{1,2})\s+de\s+"
    r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)"
    r"\s+de\s+(\d{4})\b"
    r"|\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b",
    re.IGNORECASE,
)

# Partes del juicio
_RE_QUEJOSO = re.compile(
    r"(?:quejoso?|parte\s+quejosa?)[:\s]+([A-ZÁÉÍÓÚÑ][^\n,;\.]{2,60})",
    re.IGNORECASE,
)
_RE_PROMOVENTE = re.compile(
    r"(?:promovente|promovente\s+quejoso?)[:\s]+([A-ZÁÉÍÓÚÑ][^\n,;\.]{2,60})",
    re.IGNORECASE,
)
_RE_ACTOR = re.compile(
    r"(?:actor|actora|demandante)[:\s]+([A-ZÁÉÍÓÚÑ][^\n,;\.]{2,60})",
    re.IGNORECASE,
)
_RE_DEMANDADO = re.compile(
    r"(?:demandado?|demandada?|parte\s+demandada?)[:\s]+([A-ZÁÉÍÓÚÑ][^\n,;\.]{2,60})",
    re.IGNORECASE,
)
_RE_AUTORIDAD = re.compile(
    r"(?:autoridad\s+responsable|tercero\s+perjudicado)[:\s]+([A-ZÁÉÍÓÚÑ][^\n,;\.]{2,80})",
    re.IGNORECASE,
)

# Tribunales mexicanos
_RE_TRIBUNAL = re.compile(
    r"((?:primer|segundo|tercer|cuarto|quinto|sexto|séptimo|octavo|noveno|décimo)?\s*"
    r"(?:tribunal\s+colegiado|juzgado\s+de\s+distrito|sala\s+regional|"
    r"suprema\s+corte|tribunal\s+unitario|tribunal\s+electoral|sala\s+superior|"
    r"consejo\s+de\s+la\s+judicatura)"
    r"[^\n]{0,80})",
    re.IGNORECASE,
)

# Circuito/Distrito
_RE_CIRCUITO = re.compile(
    r"(\w+(?:\s+\w+){0,3})\s+circuito",
    re.IGNORECASE,
)

# Artículos citados
_RE_ARTICULO = re.compile(
    r"\bart[íi]culo\s+(\d+(?:\s*[,y]\s*\d+)*)\s+(?:de\s+la\s+|del\s+)?([A-ZÁÉÍÓÚÑ][^\n]{0,60})",
    re.IGNORECASE,
)

# Leyes y códigos
_RE_LEY = re.compile(
    r"((?:ley|código|reglamento|constitución)\s+[A-ZÁÉÍÓÚÑ][^\n]{3,80}?)"
    r"(?=\s*[,\.\n;])",
    re.IGNORECASE,
)

# Sentido de la resolución
_RE_SENTIDO = re.compile(
    r"\b(amparo\s+(?:concedido|negado|sobreseído)|"
    r"queja\s+fundada|queja\s+infundada|"
    r"incompetencia|confirmad[ao]|revocad[ao]|modificad[ao]|"
    r"condena|absuelto?|sobreseimiento)\b",
    re.IGNORECASE,
)


# ─── Main extractor class ─────────────────────────────────────────────────────

class EntityExtractor:
    """
    Extracts structured legal entities from Spanish legal document text.
    Combines spaCy NER with hand-crafted regex patterns.
    """

    def extract(self, text: str) -> Dict[str, Any]:
        """
        Main entry point. Returns a dict with all extracted entity groups.
        Safe to call even with empty / very long text.
        """
        # Work on first ~15 000 chars for speed (covers most headers & body)
        sample = text[:15_000]

        entities: Dict[str, Any] = {
            "expedientes":  self._extract_list(_RE_EXPEDIENTE, sample, group=1),
            "folios":       self._extract_list(_RE_FOLIO, sample, group=1),
            "fechas":       self._extract_fechas(sample),
            "quejosos":     self._extract_list(_RE_QUEJOSO, sample, group=1),
            "promoventes":  self._extract_list(_RE_PROMOVENTE, sample, group=1),
            "actores":      self._extract_list(_RE_ACTOR, sample, group=1),
            "demandados":   self._extract_list(_RE_DEMANDADO, sample, group=1),
            "autoridades":  self._extract_list(_RE_AUTORIDAD, sample, group=1),
            "tribunales":   self._extract_list(_RE_TRIBUNAL, sample, group=1),
            "circuitos":    self._extract_list(_RE_CIRCUITO, sample, group=1),
            "articulos":    self._extract_articulos(sample),
            "leyes":        self._extract_list(_RE_LEY, sample, group=1),
            "sentido":      self._extract_list(_RE_SENTIDO, sample, group=1),
            "personas":     [],
            "organizaciones": [],
        }

        # Augment with spaCy NER if available
        if _SPACY_OK and _nlp:
            entities = self._augment_with_spacy(text[:5_000], entities)

        # Deduplicate and clean
        for key, val in entities.items():
            if isinstance(val, list):
                entities[key] = list(dict.fromkeys(
                    v.strip() for v in val if v and v.strip()
                ))

        return entities

    # ─── Regex helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _extract_list(pattern: re.Pattern, text: str, group: int = 0) -> List[str]:
        matches = pattern.findall(text)
        results = []
        for m in matches:
            val = m[group - 1] if isinstance(m, tuple) else m
            val = val.strip()
            if val:
                results.append(val)
        return results

    @staticmethod
    def _extract_fechas(text: str) -> List[str]:
        results = []
        for m in _RE_FECHA.finditer(text):
            if m.group(1):  # "12 de enero de 2024"
                results.append(f"{m.group(1)} de {m.group(2)} de {m.group(3)}")
            elif m.group(4):  # "12/01/2024"
                results.append(f"{m.group(4)}/{m.group(5)}/{m.group(6)}")
        return results

    @staticmethod
    def _extract_articulos(text: str) -> List[str]:
        results = []
        for m in _RE_ARTICULO.finditer(text):
            nums = m.group(1).strip()
            ley  = m.group(2).strip()[:60]
            results.append(f"Art. {nums} de {ley}")
        return results

    # ─── spaCy augmentation ───────────────────────────────────────────────────

    @staticmethod
    def _augment_with_spacy(text: str, entities: Dict) -> Dict:
        try:
            doc = _nlp(text)
            for ent in doc.ents:
                if ent.label_ == "PER":
                    entities["personas"].append(ent.text)
                elif ent.label_ in ("ORG", "GPE"):
                    entities["organizaciones"].append(ent.text)
        except Exception as exc:
            logger.warning(f"spaCy NER failed: {exc}")
        return entities


# ─── Module-level singleton ───────────────────────────────────────────────────
_extractor: EntityExtractor | None = None


def get_extractor() -> EntityExtractor:
    global _extractor
    if _extractor is None:
        _extractor = EntityExtractor()
    return _extractor


def extract_entities(text: str) -> Dict[str, Any]:
    """Convenience function — uses the module-level singleton."""
    return get_extractor().extract(text)

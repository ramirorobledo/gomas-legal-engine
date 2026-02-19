import yaml
import re
import os
import logging
from typing import Dict, List, Tuple, Any

# Load rules
RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.yaml")

logger = logging.getLogger(__name__)

class DocumentClassifier:
    def __init__(self):
        self.rules = self._load_rules()

    def _load_rules(self) -> List[Dict]:
        if not os.path.exists(RULES_PATH):
            logger.warning("Rules file not found. Classification will fail.")
            return []
        with open(RULES_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or []

    def classify(self, text: str, pages_count: int = 0) -> Tuple[str, float, List[str]]:
        """
        Analyzes text against loaded rules.
        Returns (document_type, confidence_score, tags)
        """
        best_type = "sin_clasificar"
        best_score = 0.0
        best_tags = []

        # Simplify checking locations by splitting text roughly
        # This is a heuristic. For better precision, we'd use the page JSON data.
        # For now, we assume 'text' is the full document text.
        text_lower = text.lower()
        
        # Heuristic for "first pages" vs "last pages"
        lines = text_lower.split('\n')
        total_lines = len(lines)
        header_region = "\n".join(lines[:min(50, total_lines)]) # First ~50 lines
        footer_region = "\n".join(lines[max(0, total_lines-50):]) # Last ~50 lines
        first_pages_region = "\n".join(lines[:min(300, total_lines)]) # Roughly first 3-5 pages depending on density

        # Iterate rules
        for rule in self.rules:
            current_score = 0.0
            matched_signals = 0
            
            for signal in rule.get('señales_fuertes', []):
                pattern = signal['texto'].lower()
                location = signal.get('ubicacion', 'cualquiera')
                weight = signal.get('peso', 0.1)
                
                match_found = False
                
                if location == 'encabezado' or location == 'inicio':
                    if pattern in header_region:
                        match_found = True
                elif location == 'ultimas_2_paginas' or location == 'cierre':
                    if pattern in footer_region:
                        match_found = True
                elif location.startswith('primeras_'):
                    if pattern in first_pages_region:
                        match_found = True
                else:
                    # 'cuerpo' or 'cualquiera'
                    if pattern in text_lower:
                        match_found = True
                
                if match_found:
                    current_score += weight
                    matched_signals += 1
            
            # Cap score at 1.0
            current_score = min(current_score, 1.0)
            
            if current_score > best_score:
                best_score = current_score
                best_type = rule['tipo']
                best_tags = rule.get('etiquetas', [])

        # Check threshold
        # We return the best guess, caller decides if it needs review based on score
        
        return best_type, best_score, best_tags

CLASSIFIER_INSTANCE = DocumentClassifier()

def classify_document(text: str) -> Dict[str, Any]:
    doc_type, confidence, tags = CLASSIFIER_INSTANCE.classify(text)
    
    requires_review = True
    found_rule = False
    
    for rule in CLASSIFIER_INSTANCE.rules:
        if rule['tipo'] == doc_type:
            found_rule = True
            if confidence >= rule.get('umbral_confianza_alta', 0.7):
                requires_review = False
            break
    
    if not found_rule and doc_type != 'sin_clasificar':
         # Fallback default threshold
         if confidence >= 0.7:
             requires_review = False

    if doc_type == 'sin_clasificar':
        requires_review = True
        
    return {
        "tipo": doc_type,
        "confianza": confidence,
        "etiquetas": tags,
        "requiere_revision": requires_review
    }

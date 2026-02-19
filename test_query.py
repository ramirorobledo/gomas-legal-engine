import unittest
import asyncio
import os
import json
import shutil
from unittest.mock import patch, MagicMock
import search_engine

# Mock Index Data
MOCK_INDEX = {
    "title": "Documento de Prueba",
    "summary": "Este es un resumen del documento.",
    "1": {
        "title": "Capítulo 1",
        "summary": "Resumen del capítulo 1.",
        "1.1": {
            "title": "Sección 1.1",
            "summary": "Detalle de la sección 1.1"
        }
    }
}

class TestSearchEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_indices"
        os.makedirs(self.test_dir, exist_ok=True)
        
        # Create a mock index file
        self.doc_id = "test_doc_1"
        with open(os.path.join(self.test_dir, f"index_{self.doc_id}.json"), 'w', encoding='utf-8') as f:
            json.dump(MOCK_INDEX, f)
            
        self.engine = search_engine.SearchEngine(self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_list_documents(self):
        docs = self.engine.list_documents()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]['id'], self.doc_id)

    @patch('llm_utils.generate_completion')
    def test_query_flow(self, mock_llm):
        # Mock LLM response
        mock_llm.return_value = "Esta es una respuesta simulada basada en el contexto."
        
        # Run async test
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.engine.query("¿Qué dice el capítulo 1?"))
        
        self.assertEqual(result['answer'], "Esta es una respuesta simulada basada en el contexto.")
        self.assertIn(self.doc_id, result['sources'])
        
        # Verify LLM was called with context containing our summaries
        args, _ = mock_llm.call_args
        prompt = args[0]
        self.assertIn("Resumen del capítulo 1", prompt)
        
        loop.close()

if __name__ == '__main__':
    unittest.main()

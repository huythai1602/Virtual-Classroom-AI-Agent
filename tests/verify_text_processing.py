"""
Verification script for Text Processing Enhancements
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.text_processing import TextProcessor

class TestTextProcessing(unittest.TestCase):
    def test_number_normalization(self):
        # Case 1: Standard Vietnam number
        text = "Số tiền là 100.000 đồng và 2.500.000 đồng."
        normalized = TextProcessor.normalize_text(text)
        self.assertEqual(normalized, "Số tiền là 100000 đồng và 2500000 đồng.")
        
        # Case 2: Mixed
        text = "Diện tích 3.4km2" # Should not be affected (no 3 digit follow)
        normalized = TextProcessor.normalize_text(text)
        self.assertEqual(normalized, "Diện tích 3.4km2") 

    def test_sentence_splitting_vn(self):
        text = "Xin chào. Tôi là AI 100.000. Bạn khỏe không?"
        sentences = TextProcessor.split_sentences_vn(text)
        
        # Expectation: 3 sentences. Number 100.000 should be normalized to 100000 inside too.
        self.assertEqual(len(sentences), 3)
        self.assertEqual(sentences[0], "Xin chào.")
        self.assertIn("100000", sentences[1])

if __name__ == "__main__":
    unittest.main()

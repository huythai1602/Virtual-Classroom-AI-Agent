"""
Verification Script for Ingestion Service
Mocks DB interactions to test logic flow.
"""
import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ingestion.processor import IngestionService

class TestIngestion(unittest.TestCase):
    def setUp(self):
        # Mock DB functions before initializing service if it imports them at top level
        # Since they are imported at top level in processor.py, we need to patch them there
        self.patcher1 = patch('services.ingestion.processor.insert_lesson')
        self.patcher2 = patch('services.ingestion.processor.update_lesson_status')
        self.patcher3 = patch('services.ingestion.processor.insert_chunks_batch')
        self.patcher4 = patch('services.ingestion.processor.get_lesson')
        
        self.mock_insert_lesson = self.patcher1.start()
        self.mock_update_lesson = self.patcher2.start()
        self.mock_insert_chunks = self.patcher3.start()
        self.mock_get_lesson = self.patcher4.start()
        
        self.service = IngestionService()
        
        # Mock processor (TextProcessor) to avoid OpenAI calls
        self.service.processor = MagicMock()
        self.service.processor.semantic_chunk.return_value = ["chunk1", "chunk2"]
        self.service.processor.get_embedding.return_value = [0.1, 0.2, 0.3]

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        self.patcher3.stop()
        self.patcher4.stop()

    def test_filename_parsing_standard(self):
        filename = "Toán lớp 4 Bài 5 Phân số - abc.txt"
        meta = self.service.parse_filename(filename)
        self.assertEqual(meta["grade"], 4)
        self.assertEqual(meta["lesson_number"], 5)
        self.assertEqual(meta["title"], "Phân số")
        self.assertEqual(meta["lesson_id"], "toan-lop-4-bai-5")

    def test_filename_parsing_legacy(self):
        filename = "bai_3_hinh_hoc.txt"
        meta = self.service.parse_filename(filename)
        self.assertEqual(meta["lesson_id"], "toan-lop-4-bai-3")
        self.assertEqual(meta["title"], "Hinh Hoc")

    def test_process_file_success(self):
        # Setup mocks
        self.mock_get_lesson.return_value = None # No existing lesson
        
        # Create dummy file
        test_file = Path("test_lesson.txt")
        test_file.write_text("Nội dung bài học test.", encoding="utf-8")
        
        try:
            result = self.service.process_file(str(test_file))
            
            # Assertions
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["chunks_count"], 2)
            
            # Verify DB calls
            self.mock_insert_lesson.assert_called_once()
            self.mock_insert_chunks.assert_called_once()
            self.mock_update_lesson.assert_called_with("test_lesson", "indexed", 2)
            
        finally:
             if test_file.exists():
                 test_file.unlink()

if __name__ == '__main__':
    unittest.main()

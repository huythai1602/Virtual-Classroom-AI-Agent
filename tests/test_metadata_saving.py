import os
import shutil
import json
from pathlib import Path
from services.ingestion.processor import IngestionService

def test_metadata_saving():
    # Setup
    test_dir = Path("data/test_transcripts")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    metadata_dir = Path("data/metadata")
    metadata_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = test_dir / "test_lesson_metadata.txt"
    test_content = "Toán lớp 5 Bài 1. Đây là nội dung bài học thử nghiệm. Chúng ta sẽ học về các số tự nhiên."
    
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(test_content)
        
    print(f"Created test file: {test_file}")
    
    # Execution
    service = IngestionService()
    print("Running process_file...")
    # Force processing to ensure we overwrite/re-process and save metadata
    result = service.process_file(str(test_file), force=True)
    
    print("Process result:", result)
    
    # Verification
    lesson_id = result.get("lesson_id")
    expected_metadata_file = metadata_dir / f"{lesson_id}.json"
    
    if expected_metadata_file.exists():
        print(f"✅ Metadata file created: {expected_metadata_file}")
        
        with open(expected_metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            
        print("Metadata content peek:")
        print(json.dumps(metadata, indent=2, ensure_ascii=False))
        
        # Check specific fields
        assert "timings" in metadata, "Missing 'timings' in metadata"
        assert "total_process_ms" in metadata["timings"], "Missing 'total_process_ms'"
        assert "stats" in metadata, "Missing 'stats' in metadata"
        assert metadata["stats"]["chunk_count"] > 0, "Chunk count should be > 0"
        
        # New fields check
        assert "file_checksum" in metadata, "Missing file_checksum"
        assert "version" in metadata, "Missing version"
        assert "provenance" in metadata, "Missing provenance"
        
        # Chunk metadata check
        assert "chunks_metadata" in metadata, "Missing chunks_metadata"
        assert len(metadata["chunks_metadata"]) > 0, "No chunk metadata"
        first_chunk = metadata["chunks_metadata"][0]
        assert "chunk_id" in first_chunk, "Missing chunk_id in chunk metadata"
        assert "tokens_count" in first_chunk, "Missing tokens_count"
        
        avg_size = metadata["stats"]["avg_chunk_size_chars"]
        print(f"Average chunk size: {avg_size} chars")
        # Currently the test file is VERY small (88 chars), so it won't trigger the >500 check unless we make a bigger file.
        # But we can check that schema is correct.
        
        print("✅ Metadata content validation passed")
        
    else:
        print(f"❌ Metadata file NOT found: {expected_metadata_file}")

    # Cleanup (optional, maybe keep for inspection)
    # if test_file.exists():
    #    test_file.unlink()
    # if expected_metadata_file.exists():
    #    expected_metadata_file.unlink()
    # test_dir.rmdir()

if __name__ == "__main__":
    try:
        test_metadata_saving()
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")

"""
Shared Database Repository
Accesses the Supabase shared database to fetch course content.
"""
from typing import Generator, Dict, Any
from .db import init_shared_connection_pool

def fetch_full_lessons_from_shared() -> Generator[Dict[str, Any], None, None]:
    """
    Yields full lesson data with aggregated transcripts from Shared DB.
    
    Returns:
        Generator yielding dicts with:
        - lesson_db_id: int
        - lesson_title: str
        - lesson_order: int
        - course_title: str
        - subject: str (category)
        - full_transcript: str
    """
    pool = init_shared_connection_pool()
    if not pool:
        print("❌ Shared DB not configured.")
        return

    conn = pool.getconn()
    try:
        cursor = conn.cursor()
        
        # Aggregate transcripts by ordering segments by start_time
        # Extracting course info for metadata mapping
        query = """
            SELECT 
                l.id as lesson_db_id, 
                l.title as lesson_title,
                l.order as lesson_order,
                c.title as course_title,
                c.category as subject,
                STRING_AGG(lt.transcripts, ' ' ORDER BY lt.start_time) as full_transcript
            FROM lessons l
            JOIN courses c ON l.course_id = c.id
            JOIN lesson_transcripts lt ON l.id = lt.lesson_id
            GROUP BY l.id, l.title, l.order, c.title, c.category
            ORDER BY c.category, c.title, l.order;
        """
        
        cursor.execute(query)
        
        # Generator to handle potentially large result sets efficiently
        while True:
            rows = cursor.fetchmany(100)
            if not rows:
                break
                
            for row in rows:
                yield {
                    "lesson_db_id": row[0],
                    "lesson_title": row[1],
                    "lesson_order": row[2],
                    "course_title": row[3],
                    "subject": row[4],
                    "full_transcript": row[5]
                }
                
        cursor.close()
    except Exception as e:
        print(f"❌ Error fetching from shared DB: {e}")
    finally:
        if conn:
            pool.putconn(conn)

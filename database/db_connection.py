"""
PostgreSQL connection management with connection pooling
"""

import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
import os
from dotenv import load_dotenv

load_dotenv()

# Global connection pool
connection_pool = None


def init_connection_pool():
    """Initialize PostgreSQL connection pool"""
    global connection_pool
    
    if connection_pool is None:
        try:
            connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", 5432)),
                database=os.getenv("POSTGRES_DB", "virtual_classroom"),
                user=os.getenv("POSTGRES_USER", "agent_user"),
                password=os.getenv("POSTGRES_PASSWORD")
            )
            print("✅ PostgreSQL connection pool initialized")
        except Exception as e:
            print(f"❌ Failed to initialize connection pool: {e}")
            raise
    
    return connection_pool


@contextmanager
def get_db_connection():
    """
    Context manager for database connection
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lessons")
    """
    pool = init_connection_pool()
    conn = None
    
    try:
        conn = pool.getconn()
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            pool.putconn(conn)


def test_connection():
    """Test PostgreSQL connection and pgvector extension"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Test basic connection
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            print(f"✅ PostgreSQL connected: {version[0][:50]}...")
            
            # Check pgvector extension
            cursor.execute("SELECT * FROM pg_extension WHERE extname = 'vector';")
            if cursor.fetchone():
                print("✅ pgvector extension is enabled")
            else:
                print("⚠️  pgvector extension NOT found. Run: CREATE EXTENSION vector;")
            
            cursor.close()
            return True
            
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


def close_connection_pool():
    """Close all connections in the pool"""
    global connection_pool
    
    if connection_pool:
        connection_pool.closeall()
        connection_pool = None
        print("✅ Connection pool closed")

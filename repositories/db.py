"""
Database connection management
Consolidated from database/db_connection.py
"""
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager

from config.settings import settings

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
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                database=settings.POSTGRES_DB,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD
            )
            print("✅ PostgreSQL connection pool initialized")
        except Exception as e:
            print(f"❌ Failed to initialize connection pool: {e}")
            raise
    
    return connection_pool


@contextmanager
def get_connection():
    """
    Context manager for database connection
    
    Usage:
        with get_connection() as conn:
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
        if conn and not conn.closed:
            try:
                conn.rollback()
            except Exception:
                pass
        raise e
    finally:
        if conn:
            try:
                pool.putconn(conn)
            except Exception:
                pass


def test_connection() -> bool:
    """Test database connection"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False

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
shared_connection_pool = None


def init_connection_pool():
    """Initialize PostgreSQL connection pool"""
    global connection_pool
    
    if connection_pool is None:
        try:
            # Use ThreadedConnectionPool for better compatibility with FastAPI's potential threading
            connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                database=settings.POSTGRES_DB,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                # Keepalives to prevent idle connection drops
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5
            )
            print("✅ PostgreSQL connection pool initialized")
        except Exception as e:
            print(f"❌ Failed to initialize connection pool: {e}")
            raise
    
    return connection_pool


def init_shared_connection_pool():
    """
    DEPRECATED: Shared PostgreSQL connection pool (Supabase)
    This function is kept for compatibility but will always return None.
    Use RabbitMQ RPC for accessing shared data.
    """
    print("⚠️ Shared database connection is DEPRECATED. Use RabbitMQ Service.")
    return None


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
        
        # Liveness check
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        except (psycopg2.OperationalError, psycopg2.InterfaceError, psycopg2.DatabaseError):
            # Connection is dead, remove it and create a new one
            print("⚠️ Connection dead, resetting...")
            # Ideally we'd remove it from pool, but SimpleConnectionPool is limited.
            # We can try to close it and let the pool eventually realize or just replace it?
            # SimpleConnectionPool doesn't natively support "replace this specific connection".
            # Hack: Put it back closed/bad, then get a new one?
            # Better: The pool creates connections on demand up to maxconn. 
            # If we don't put it back, the pool eventually runs out?
            # Actually psycopg2 pool putconn has 'close' param:
            # "If close is True, the connection is closed and discarded from the pool." 
            # (Wait, actually putconn(conn, key=None, close=False))
            # If close=True, the connection is closed *by the pool*? 
            # Checking source: putconn just adds it back to list. If close=True, it calls conn.close().
            # So we should put it back with close=True, effectively shrinking the pool size? 
            # Then getconn will create a NEW one if pool is below min?
            # SimpleConnectionPool behavior: 
            # If we discard one, the pool count decreases. Next getconn should create one if needed or get another available.
            
            pool.putconn(conn, close=True) # Discard dead connection
            conn = pool.getconn() # Get a fresh one
            
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
                # Only put back if it's still usable (open)
                # If we detected it was closed/dead in the block, we might want to discard it?
                # But for simplicity, put it back. If it broke during use, next check will kill it.
                is_closed = conn.closed
                pool.putconn(conn, close=bool(is_closed)) 
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


@contextmanager
def get_shared_connection():
    """
    DEPRECATED: Shared database connection
    """
    print("⚠️ Use of get_shared_connection is DEPRECATED. Please use RabbitMQ RPC.")
    yield None

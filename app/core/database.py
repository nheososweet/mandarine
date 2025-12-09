from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool, QueuePool
from .config import settings
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE ENGINE CONFIGURATION
# =============================================================================

# Create database engine with advanced configuration
engine = create_engine(
    settings.DATABASE_URL,
    
    # Connection pool settings
    poolclass=QueuePool,  # Use QueuePool for better connection management
    pool_size=settings.DB_POOL_SIZE,  # Number of connections to keep open
    max_overflow=settings.DB_MAX_OVERFLOW,  # Max connections beyond pool_size
    pool_timeout=settings.DB_POOL_TIMEOUT,  # Seconds to wait for connection
    pool_recycle=settings.DB_POOL_RECYCLE,  # Recycle connections after N seconds
    
    # Connection behavior
    pool_pre_ping=True,  # Test connection before using (detect disconnects)
    
    # SQL echo - useful for debugging
    echo=settings.DB_ECHO_SQL,  # Print all SQL queries to console
    
    # Connection arguments
    connect_args={
        "connect_timeout": 10,  # Connection timeout in seconds
    }
)


# =============================================================================
# SESSION CONFIGURATION
# =============================================================================

# Create SessionLocal class for database sessions
SessionLocal = sessionmaker(
    autocommit=False,  # Don't auto-commit transactions
    autoflush=False,   # Don't auto-flush before queries
    bind=engine,
    expire_on_commit=False  # Don't expire objects after commit
)

# Create Base class for models
Base = declarative_base()


# =============================================================================
# DATABASE SESSION DEPENDENCY
# =============================================================================

def get_db() -> Session:
    """
    Database session dependency for FastAPI endpoints.
    
    Usage in endpoints:
        @router.get("/users/")
        def get_users(db: Session = Depends(get_db)):
            users = db.query(User).all()
            return users
    
    This function:
    1. Creates a new database session
    2. Yields it to the endpoint
    3. Closes the session after the request (even if error occurs)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# DATABASE UTILITIES
# =============================================================================

def create_database_tables():
    """
    Create all database tables defined in models.
    
    ⚠️ WARNING: Only use this in development!
    In production, use Alembic migrations instead.
    """
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables created successfully!")


def drop_database_tables():
    """
    Drop all database tables.
    
    ⚠️ DANGER: This will delete all data!
    Only use in development/testing.
    """
    logger.warning("⚠️ Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.info("✅ Database tables dropped!")


def check_database_connection() -> bool:
    """
    Check if database connection is working.
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        # Try to connect and execute a simple query
        with engine.connect() as connection:
            connection.execute("SELECT 1")
        logger.info("✅ Database connection successful!")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False


# =============================================================================
# EVENT LISTENERS (Advanced)
# =============================================================================

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """
    Event listener for new database connections.
    Can be used to set connection-specific settings.
    """
    if settings.DEBUG:
        logger.debug(f"New database connection established")


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """
    Event listener when connection is retrieved from pool.
    """
    if settings.DEBUG:
        logger.debug("Connection checked out from pool")


# =============================================================================
# INITIALIZATION
# =============================================================================

def init_db():
    """
    Initialize database.
    Run this when starting the application.
    """
    logger.info("Initializing database...")
    
    # Check connection
    if not check_database_connection():
        raise Exception("Cannot connect to database!")
    
    # In development, you can create tables here
    # In production, use Alembic migrations
    if settings.DEBUG:
        logger.info("Debug mode: Checking database tables...")
        # create_database_tables()  # Uncomment if you want auto-create tables
    
    logger.info("✅ Database initialized successfully!")


# =============================================================================
# TEST DATABASE CONNECTION
# =============================================================================

if __name__ == "__main__":
    """Test database connection when running this file directly."""
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "=" * 80)
    print("🔍 TESTING DATABASE CONNECTION")
    print("=" * 80)
    
    from .config import print_config
    print_config()
    
    print("\n" + "-" * 80)
    print("Testing connection...")
    print("-" * 80)
    
    if check_database_connection():
        print("✅ Connection successful!")
        
        # Try to get a session
        try:
            db = SessionLocal()
            print("✅ Session created successfully!")
            db.close()
            print("✅ Session closed successfully!")
        except Exception as e:
            print(f"❌ Session creation failed: {e}")
    else:
        print("❌ Connection failed!")
    
    print("=" * 80 + "\n")
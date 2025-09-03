"""
Database engine helper utilities for consistent engine access across the application.
"""
import logging
from flask import current_app

logger = logging.getLogger(__name__)

def get_db_engine():
    """
    Get the SQLAlchemy engine from the current Flask app context.
    
    This provides a standardized way to access the database engine across
    different parts of the application, handling various Flask-SQLAlchemy
    version differences.
    
    Returns:
        sqlalchemy.engine.Engine: The database engine
        
    Raises:
        RuntimeError: If no engine can be obtained
    """
    # Try to get engine from Flask-SQLAlchemy extension
    sa_ext = current_app.extensions.get('sqlalchemy')
    
    if sa_ext:
        # Try common attribute patterns across Flask-SQLAlchemy versions
        if hasattr(sa_ext, 'db') and hasattr(sa_ext.db, 'engine'):
            logger.debug("get_db_engine: using engine via sa_ext.db.engine")
            return sa_ext.db.engine
        elif hasattr(sa_ext, 'engine'):
            logger.debug("get_db_engine: using engine via sa_ext.engine")
            return sa_ext.engine
        elif hasattr(sa_ext, 'engines'):
            try:
                engine = sa_ext.engines[current_app]
                logger.debug("get_db_engine: using engine via sa_ext.engines[current_app]")
                return engine
            except Exception as e:
                logger.warning(f"get_db_engine: failed sa_ext.engines lookup: {e}")
    
    # Last-resort fallback: import db from app
    try:
        from app import db as app_db
        logger.warning("get_db_engine: fell back to importing db from app (monitor for binding issues)")
        return app_db.engine
    except Exception as e:
        logger.error(f"get_db_engine: failed to obtain engine from app db: {e}")
        raise RuntimeError(f"Could not obtain database engine: {e}")

"""
Database module for HPS SVT Component Tracker

This module handles database initialization, schema creation, and connection management.
"""
import sqlite3
import os
from pathlib import Path
from datetime import datetime
from typing import Optional


# Default database location
DEFAULT_DB_PATH = os.path.expanduser("~/.hps_svt_tracker/svt_components.db")
DEFAULT_DATA_DIR = os.path.expanduser("~/.hps_svt_tracker/test_data")


class Database:
    """Database connection and schema management"""
    
    def __init__(self, db_path: str = DEFAULT_DB_PATH, data_dir: str = DEFAULT_DATA_DIR):
        self.db_path = db_path
        self.data_dir = data_dir
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)
        
    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection with foreign keys enabled"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        return conn
    
    def initialize_schema(self):
        """Create all database tables"""
        with self.get_connection() as conn:
            # Components table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS components (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    
                    -- Permanent Identity
                    serial_number TEXT UNIQUE,
                    asset_tag TEXT,
                    manufacturer TEXT,
                    manufacture_date DATE,
                    
                    -- Current State
                    installation_status TEXT NOT NULL,
                    current_location TEXT,
                    installed_position TEXT,
                    
                    -- Type-specific attributes (JSON)
                    attributes_json TEXT,
                    
                    -- Metadata
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    CHECK (type IN ('module', 'feb', 'cable', 'optical_board', 
                                   'mpod_module', 'mpod_crate', 'flange_board', 'other')),
                    CHECK (installation_status IN ('installed', 'spare', 'incoming', 
                                                   'testing', 'qualified', 'failed', 
                                                   'repair', 'degraded', 'retired', 'lost'))
                )
            """)
            
            # Installation history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS installation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    component_id TEXT NOT NULL,
                    position TEXT NOT NULL,
                    installation_date TIMESTAMP NOT NULL,
                    removal_date TIMESTAMP,
                    installed_by TEXT,
                    removed_by TEXT,
                    removal_reason TEXT,
                    run_period TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (component_id) REFERENCES components(id)
                )
            """)
            
            # Test results table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    component_id TEXT NOT NULL,
                    test_date TIMESTAMP NOT NULL,
                    test_type TEXT NOT NULL,
                    
                    -- Simple measurements
                    pass_fail BOOLEAN,
                    voltage_measured REAL,
                    current_measured REAL,
                    noise_level REAL,
                    temperature REAL,
                    
                    -- Complex data as JSON
                    measurements_json TEXT,
                    
                    -- File references (relative paths from data_dir)
                    image_paths TEXT,
                    data_file_path TEXT,
                    
                    -- Metadata
                    tested_by TEXT,
                    test_setup TEXT,
                    test_conditions TEXT,
                    notes TEXT,
                    
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (component_id) REFERENCES components(id)
                )
            """)
            
            # Component connections table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    component_a_id TEXT NOT NULL,
                    component_b_id TEXT NOT NULL,
                    connection_type TEXT,
                    cable_id TEXT,
                    installation_date DATE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (component_a_id) REFERENCES components(id),
                    FOREIGN KEY (component_b_id) REFERENCES components(id),
                    FOREIGN KEY (cable_id) REFERENCES components(id)
                )
            """)
            
            # Maintenance log table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS maintenance_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    component_id TEXT NOT NULL,
                    log_date TIMESTAMP NOT NULL,
                    log_type TEXT,
                    severity TEXT,
                    description TEXT,
                    resolution TEXT,
                    resolved_date DATE,
                    logged_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (component_id) REFERENCES components(id),
                    CHECK (log_type IN ('issue', 'repair', 'maintenance', 'note')),
                    CHECK (severity IN ('critical', 'warning', 'info'))
                )
            """)
            
            # Create useful indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_components_type ON components(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_components_status ON components(installation_status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_components_position ON components(installed_position)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_test_results_component ON test_results(component_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_test_results_date ON test_results(test_date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_installation_history_component ON installation_history(component_id)")
            
            conn.commit()
    
    def reset_database(self):
        """Drop all tables and recreate schema - USE WITH CAUTION"""
        with self.get_connection() as conn:
            # Drop all tables
            conn.execute("DROP TABLE IF EXISTS maintenance_log")
            conn.execute("DROP TABLE IF EXISTS connections")
            conn.execute("DROP TABLE IF EXISTS test_results")
            conn.execute("DROP TABLE IF EXISTS installation_history")
            conn.execute("DROP TABLE IF EXISTS components")
            conn.commit()
        
        # Recreate
        self.initialize_schema()
    
    def backup_database(self, backup_path: Optional[str] = None):
        """Create a backup of the database"""
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.db_path}.backup_{timestamp}"
        
        import shutil
        shutil.copy2(self.db_path, backup_path)
        return backup_path


def get_default_db() -> Database:
    """Get the default database instance"""
    db = Database()
    # Initialize schema if database doesn't exist
    if not os.path.exists(db.db_path):
        db.initialize_schema()
    return db

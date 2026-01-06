"""
Models for HPS SVT Component Tracker

This module provides classes and functions for working with components,
test results, and other database entities.
"""
import json
import os
import shutil
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from .database import Database, get_default_db


class Component:
    """Represents a component in the SVT system"""
    
    # Valid component types
    TYPES = ['module', 'hybrid', 'sensor', 'feb', 'cable', 'optical_board',
             'mpod_module', 'mpod_crate', 'flange_board', 'other']
    
    # Valid installation statuses
    STATUSES = ['installed', 'spare', 'incoming', 'testing', 'qualified', 
                'failed', 'repair', 'degraded', 'retired', 'lost']
    
    def __init__(self, id: str, type: str, installation_status: str = 'incoming',
                 serial_number: Optional[str] = None,
                 manufacturer: Optional[str] = None,
                 current_location: Optional[str] = None,
                 attributes: Optional[Dict[str, Any]] = None,
                 **kwargs):
        """
        Initialize a component
        
        Args:
            id: Component ID (typically manufacturer serial number)
            type: Component type (module, feb, cable, etc.)
            installation_status: Current status
            serial_number: Manufacturer serial number (if different from id)
            manufacturer: Manufacturer name
            current_location: Current physical location
            attributes: Type-specific attributes dict
        """
        if type not in self.TYPES:
            raise ValueError(f"Invalid component type: {type}. Must be one of {self.TYPES}")
        if installation_status not in self.STATUSES:
            raise ValueError(f"Invalid status: {installation_status}. Must be one of {self.STATUSES}")
        
        self.id = id
        self.type = type
        self.installation_status = installation_status
        self.serial_number = serial_number or id
        self.manufacturer = manufacturer
        self.current_location = current_location
        self.installed_position = kwargs.get('installed_position')
        self.asset_tag = kwargs.get('asset_tag')
        self.manufacture_date = kwargs.get('manufacture_date')
        self.notes = kwargs.get('notes')
        self.assembled_sensor_id = kwargs.get('assembled_sensor_id')
        self.assembled_hybrid_id = kwargs.get('assembled_hybrid_id')
        self.attributes = attributes or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert component to dictionary for database storage"""
        return {
            'id': self.id,
            'type': self.type,
            'serial_number': self.serial_number,
            'asset_tag': self.asset_tag,
            'manufacturer': self.manufacturer,
            'manufacture_date': self.manufacture_date,
            'installation_status': self.installation_status,
            'current_location': self.current_location,
            'installed_position': self.installed_position,
            'assembled_sensor_id': self.assembled_sensor_id,
            'assembled_hybrid_id': self.assembled_hybrid_id,
            'attributes_json': json.dumps(self.attributes) if self.attributes else None,
            'notes': self.notes,
        }
    
    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> 'Component':
        """Create component from database row"""
        attributes = json.loads(row['attributes_json']) if row['attributes_json'] else {}
        return cls(
            id=row['id'],
            type=row['type'],
            serial_number=row['serial_number'],
            asset_tag=row['asset_tag'],
            manufacturer=row['manufacturer'],
            manufacture_date=row['manufacture_date'],
            installation_status=row['installation_status'],
            current_location=row['current_location'],
            installed_position=row['installed_position'],
            assembled_sensor_id=row.get('assembled_sensor_id'),
            assembled_hybrid_id=row.get('assembled_hybrid_id'),
            attributes=attributes,
            notes=row['notes']
        )
    
    def save(self, db: Optional[Database] = None):
        """Save component to database"""
        if db is None:
            db = get_default_db()
        
        data = self.to_dict()
        data['updated_at'] = datetime.now().isoformat()
        
        with db.get_connection() as conn:
            # Check if component exists
            existing = conn.execute(
                "SELECT id FROM components WHERE id = ?", (self.id,)
            ).fetchone()
            
            if existing:
                # Update
                set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
                values = list(data.values()) + [self.id]
                conn.execute(
                    f"UPDATE components SET {set_clause} WHERE id = ?",
                    values
                )
            else:
                # Insert
                columns = ", ".join(data.keys())
                placeholders = ", ".join(["?" for _ in data])
                conn.execute(
                    f"INSERT INTO components ({columns}) VALUES ({placeholders})",
                    list(data.values())
                )
            conn.commit()
    
    @classmethod
    def get(cls, component_id: str, db: Optional[Database] = None) -> Optional['Component']:
        """Retrieve a component by ID"""
        if db is None:
            db = get_default_db()
        
        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM components WHERE id = ?", (component_id,)
            ).fetchone()
            
            if row:
                return cls.from_row(dict(row))
            return None
    
    @classmethod
    def list_all(cls, component_type: Optional[str] = None, 
                 status: Optional[str] = None,
                 db: Optional[Database] = None) -> List['Component']:
        """List components with optional filters"""
        if db is None:
            db = get_default_db()
        
        query = "SELECT * FROM components WHERE 1=1"
        params = []
        
        if component_type:
            query += " AND type = ?"
            params.append(component_type)
        
        if status:
            query += " AND installation_status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC"
        
        with db.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [cls.from_row(dict(row)) for row in rows]
    
    def delete(self, db: Optional[Database] = None):
        """Delete component from database"""
        if db is None:
            db = get_default_db()
        
        with db.get_connection() as conn:
            conn.execute("DELETE FROM components WHERE id = ?", (self.id,))
            conn.commit()
    
    def __repr__(self):
        return f"Component(id='{self.id}', type='{self.type}', status='{self.installation_status}')"

    # Attribute convenience methods
    def get_attribute(self, key: str, default: Any = None) -> Any:
        """
        Get a single attribute value

        Args:
            key: Attribute key
            default: Default value if key not found

        Returns:
            Attribute value or default
        """
        return self.attributes.get(key, default)

    def set_attribute(self, key: str, value: Any):
        """
        Set a single attribute value

        Args:
            key: Attribute key
            value: Attribute value
        """
        self.attributes[key] = value

    def update_attributes(self, new_attributes: Dict[str, Any], overwrite: bool = True):
        """
        Update multiple attributes at once

        Args:
            new_attributes: Dictionary of attributes to add/update
            overwrite: If True, overwrite existing keys. If False, only add new keys.
        """
        if overwrite:
            self.attributes.update(new_attributes)
        else:
            for key, value in new_attributes.items():
                if key not in self.attributes:
                    self.attributes[key] = value

    def remove_attribute(self, key: str) -> Any:
        """
        Remove an attribute and return its value

        Args:
            key: Attribute key to remove

        Returns:
            Removed value, or None if key didn't exist
        """
        return self.attributes.pop(key, None)

    def list_attributes(self) -> List[str]:
        """
        Get list of all attribute keys

        Returns:
            List of attribute key names
        """
        return list(self.attributes.keys())


class TestResult:
    """Represents a test result for a component"""

    # Valid file types for test files
    FILE_TYPES = ['raw_data', 'plot', 'image', 'log', 'other']

    def __init__(self, component_id: str, test_type: str,
                 test_date: Optional[datetime] = None,
                 pass_fail: Optional[bool] = None,
                 measurements: Optional[Dict[str, Any]] = None,
                 files: Optional[Dict[str, List[str]]] = None,
                 **kwargs):
        """
        Initialize a test result

        Args:
            component_id: ID of component being tested
            test_type: Type of test (e.g., 'iv_curve', 'noise_test')
            test_date: When test was performed (defaults to now)
            pass_fail: Test pass/fail status
            measurements: Dictionary of measurements. Each entry can be:
                - A simple value: {"leakage_current": 1.2e-9}
                - A dict with metadata: {"leakage_current": {"value": 1.2e-9, "unit": "A"}}
            files: Dictionary of file paths organized by type:
                {
                    'raw_data': ['path/to/data1.csv', 'path/to/data2.dat'],
                    'plot': ['path/to/plot1.png', 'path/to/plot2.png'],
                    'image': ['path/to/photo.jpg'],
                    'log': ['path/to/test.log'],
                    'other': ['path/to/other.txt']
                }
        """
        self.component_id = component_id
        self.test_type = test_type
        self.test_date = test_date or datetime.now()
        self.pass_fail = pass_fail
        self.measurements = measurements or {}
        self.files = files or {}
        self.tested_by = kwargs.get('tested_by')
        self.test_setup = kwargs.get('test_setup')
        self.test_conditions = kwargs.get('test_conditions')
        self.notes = kwargs.get('notes')

        # Will be populated when saved
        self.id = None
        self.stored_files = []  # List of stored file records

    def save(self, db: Optional[Database] = None):
        """Save test result to database and copy files to organized storage"""
        if db is None:
            db = get_default_db()

        # Extract simple measurements for indexed columns
        voltage = self.measurements.get('voltage_measured')
        current = self.measurements.get('current_measured')
        noise = self.measurements.get('noise_level')
        temp = self.measurements.get('temperature')

        # Handle measurements that might be dicts with metadata
        if isinstance(voltage, dict):
            voltage = voltage.get('value')
        if isinstance(current, dict):
            current = current.get('value')
        if isinstance(noise, dict):
            noise = noise.get('value')
        if isinstance(temp, dict):
            temp = temp.get('value')

        data = {
            'component_id': self.component_id,
            'test_date': self.test_date.isoformat(),
            'test_type': self.test_type,
            'pass_fail': self.pass_fail,
            'voltage_measured': voltage,
            'current_measured': current,
            'noise_level': noise,
            'temperature': temp,
            'measurements_json': json.dumps(self.measurements) if self.measurements else None,
            'tested_by': self.tested_by,
            'test_setup': self.test_setup,
            'test_conditions': self.test_conditions,
            'notes': self.notes,
        }

        with db.get_connection() as conn:
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?" for _ in data])
            cursor = conn.execute(
                f"INSERT INTO test_results ({columns}) VALUES ({placeholders})",
                list(data.values())
            )
            self.id = cursor.lastrowid
            conn.commit()

        # Store files after we have the test ID
        if self.files:
            self._store_files(db)

        return self.id

    def _store_files(self, db: Database):
        """Copy files to organized storage and record in test_files table"""
        # Create storage directory: data_dir/YYYY/component_id/YYYYMMDD_HHMMSS_testtype/
        test_dir = os.path.join(
            db.data_dir,
            self.test_date.strftime("%Y"),
            self.component_id,
            f"{self.test_date.strftime('%Y%m%d_%H%M%S')}_{self.test_type}"
        )

        with db.get_connection() as conn:
            for file_type, file_paths in self.files.items():
                if file_type not in self.FILE_TYPES:
                    print(f"Warning: Invalid file type '{file_type}', skipping")
                    continue

                # Create subdirectory for this file type
                type_dir = os.path.join(test_dir, file_type)
                os.makedirs(type_dir, exist_ok=True)

                for file_path in file_paths:
                    if not os.path.exists(file_path):
                        print(f"Warning: File not found: {file_path}")
                        continue

                    # Get original filename and size
                    original_filename = Path(file_path).name
                    file_size = os.path.getsize(file_path)

                    # Copy file to storage
                    dest_path = os.path.join(type_dir, original_filename)

                    # Handle duplicate filenames
                    counter = 1
                    while os.path.exists(dest_path):
                        name, ext = os.path.splitext(original_filename)
                        dest_path = os.path.join(type_dir, f"{name}_{counter}{ext}")
                        counter += 1

                    shutil.copy2(file_path, dest_path)

                    # Store relative path
                    rel_path = os.path.relpath(dest_path, db.data_dir)

                    # Insert into test_files table
                    conn.execute("""
                        INSERT INTO test_files
                        (test_id, file_type, file_path, original_filename, file_size)
                        VALUES (?, ?, ?, ?, ?)
                    """, (self.id, file_type, rel_path, original_filename, file_size))

                    self.stored_files.append({
                        'file_type': file_type,
                        'file_path': rel_path,
                        'original_filename': original_filename,
                        'file_size': file_size
                    })

            conn.commit()

    def add_file(self, file_path: str, file_type: str,
                 description: Optional[str] = None,
                 metadata: Optional[Dict[str, Any]] = None,
                 db: Optional[Database] = None) -> int:
        """
        Add a file to an existing test result

        Args:
            file_path: Path to the file to add
            file_type: Type of file ('raw_data', 'plot', 'image', 'log', 'other')
            description: Optional description of the file
            metadata: Optional metadata dict for the file
            db: Database instance

        Returns:
            file_id: ID of the created test_files record
        """
        if self.id is None:
            raise ValueError("Test result must be saved before adding files")

        if file_type not in self.FILE_TYPES:
            raise ValueError(f"Invalid file type: {file_type}. Must be one of {self.FILE_TYPES}")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if db is None:
            db = get_default_db()

        # Create storage directory
        test_dir = os.path.join(
            db.data_dir,
            self.test_date.strftime("%Y"),
            self.component_id,
            f"{self.test_date.strftime('%Y%m%d_%H%M%S')}_{self.test_type}",
            file_type
        )
        os.makedirs(test_dir, exist_ok=True)

        # Get file info
        original_filename = Path(file_path).name
        file_size = os.path.getsize(file_path)

        # Copy file
        dest_path = os.path.join(test_dir, original_filename)
        counter = 1
        while os.path.exists(dest_path):
            name, ext = os.path.splitext(original_filename)
            dest_path = os.path.join(test_dir, f"{name}_{counter}{ext}")
            counter += 1

        shutil.copy2(file_path, dest_path)
        rel_path = os.path.relpath(dest_path, db.data_dir)

        # Insert into database
        with db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO test_files
                (test_id, file_type, file_path, original_filename, description,
                 file_size, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (self.id, file_type, rel_path, original_filename, description,
                  file_size, json.dumps(metadata) if metadata else None))
            conn.commit()
            return cursor.lastrowid
    
    @classmethod
    def get_by_id(cls, test_id: int, db: Optional[Database] = None) -> Optional[Dict[str, Any]]:
        """Get a test result by its ID"""
        if db is None:
            db = get_default_db()

        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM test_results WHERE id = ?",
                (test_id,)
            ).fetchone()

            if row:
                return dict(row)
            return None

    @classmethod
    def get_files(cls, test_id: int, file_type: Optional[str] = None,
                  db: Optional[Database] = None) -> List[Dict[str, Any]]:
        """
        Get files associated with a test result

        Args:
            test_id: ID of the test result
            file_type: Optional filter by file type ('raw_data', 'plot', 'image', 'log', 'other')
            db: Database instance

        Returns:
            List of file records
        """
        if db is None:
            db = get_default_db()

        with db.get_connection() as conn:
            if file_type:
                rows = conn.execute("""
                    SELECT * FROM test_files
                    WHERE test_id = ? AND file_type = ?
                    ORDER BY upload_date DESC
                """, (test_id, file_type)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM test_files
                    WHERE test_id = ?
                    ORDER BY file_type, upload_date DESC
                """, (test_id,)).fetchall()

            return [dict(row) for row in rows]

    @classmethod
    def get_files_by_type(cls, test_id: int,
                          db: Optional[Database] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get files associated with a test result, organized by type

        Args:
            test_id: ID of the test result
            db: Database instance

        Returns:
            Dict with file types as keys and lists of file records as values
        """
        files = cls.get_files(test_id, db=db)
        result = {ft: [] for ft in cls.FILE_TYPES}
        for f in files:
            if f['file_type'] in result:
                result[f['file_type']].append(f)
        return result

    @classmethod
    def get_for_component(cls, component_id: str, db: Optional[Database] = None) -> List[Dict[str, Any]]:
        """Get all test results for a component"""
        if db is None:
            db = get_default_db()

        with db.get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM test_results
                   WHERE component_id = ?
                   ORDER BY test_date DESC""",
                (component_id,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    @classmethod
    def get_recent(cls, days: int = 30, db: Optional[Database] = None) -> List[Dict[str, Any]]:
        """Get test results from the last N days"""
        if db is None:
            db = get_default_db()
        
        cutoff = datetime.now().timestamp() - (days * 24 * 60 * 60)
        cutoff_date = datetime.fromtimestamp(cutoff).isoformat()
        
        with db.get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM test_results 
                   WHERE test_date >= ? 
                   ORDER BY test_date DESC""",
                (cutoff_date,)
            ).fetchall()
            return [dict(row) for row in rows]


def install_component(component_id: str, position: str, run_period: str,
                      installed_by: Optional[str] = None,
                      notes: Optional[str] = None,
                      db: Optional[Database] = None):
    """Install a component at a specific position"""
    if db is None:
        db = get_default_db()
    
    # Get component
    component = Component.get(component_id, db)
    if not component:
        raise ValueError(f"Component {component_id} not found")
    
    # Update component
    component.installation_status = 'installed'
    component.installed_position = position
    component.save(db)
    
    # Record in installation history
    with db.get_connection() as conn:
        conn.execute("""
            INSERT INTO installation_history 
            (component_id, position, installation_date, installed_by, run_period, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (component_id, position, datetime.now().isoformat(), 
              installed_by, run_period, notes))
        conn.commit()


def remove_component(component_id: str, removal_reason: str,
                    removed_by: Optional[str] = None,
                    db: Optional[Database] = None):
    """Remove a component from its installed position"""
    if db is None:
        db = get_default_db()

    # Get component
    component = Component.get(component_id, db)
    if not component:
        raise ValueError(f"Component {component_id} not found")

    # Update installation history
    with db.get_connection() as conn:
        conn.execute("""
            UPDATE installation_history
            SET removal_date = ?, removed_by = ?, removal_reason = ?
            WHERE component_id = ? AND removal_date IS NULL
        """, (datetime.now().isoformat(), removed_by, removal_reason, component_id))
        conn.commit()

    # Update component (location remains unchanged)
    component.installation_status = 'spare'
    component.installed_position = None
    component.save(db)


def update_location(component_id: str, new_location: str,
                   db: Optional[Database] = None):
    """
    Update the physical location of a component

    Args:
        component_id: ID of component to update
        new_location: New physical location
        db: Database instance
    """
    if db is None:
        db = get_default_db()

    # Get component
    component = Component.get(component_id, db)
    if not component:
        raise ValueError(f"Component {component_id} not found")

    # Update location
    component.current_location = new_location
    component.save(db)


def create_connection(component_a_id: str, component_b_id: str,
                     connection_type: Optional[str] = None,
                     cable_id: Optional[str] = None,
                     notes: Optional[str] = None,
                     db: Optional[Database] = None):
    """
    Create a connection between two components

    Args:
        component_a_id: First component (e.g., FEB ID)
        component_b_id: Second component (e.g., module ID)
        connection_type: Type of connection (e.g., 'signal', 'power', 'optical')
        cable_id: ID of cable component used (optional)
        notes: Additional notes
        db: Database instance

    Returns:
        connection_id: ID of created connection
    """
    if db is None:
        db = get_default_db()

    # Verify components exist
    comp_a = Component.get(component_a_id, db)
    comp_b = Component.get(component_b_id, db)

    if not comp_a:
        raise ValueError(f"Component {component_a_id} not found")
    if not comp_b:
        raise ValueError(f"Component {component_b_id} not found")

    # If cable specified, verify it exists
    if cable_id:
        cable = Component.get(cable_id, db)
        if not cable:
            raise ValueError(f"Cable {cable_id} not found")

    with db.get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO connections
            (component_a_id, component_b_id, connection_type, cable_id,
             installation_date, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (component_a_id, component_b_id, connection_type, cable_id,
              datetime.now().isoformat(), notes))

        conn.commit()
        return cursor.lastrowid


def get_connections_for_component(component_id: str,
                                  db: Optional[Database] = None) -> List[Dict[str, Any]]:
    """
    Get all connections for a component

    Returns list of connection records where component appears as either A or B
    """
    if db is None:
        db = get_default_db()

    with db.get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM connections
            WHERE component_a_id = ? OR component_b_id = ?
            ORDER BY installation_date DESC
        """, (component_id, component_id)).fetchall()

        return [dict(row) for row in rows]


def get_connected_components(component_id: str,
                            db: Optional[Database] = None) -> List[Dict[str, Any]]:
    """
    Get all components connected to a given component

    Returns:
        List of dicts with keys: connected_id, connection_type, cable_id
    """
    if db is None:
        db = get_default_db()

    with db.get_connection() as conn:
        # Get connections where component is A
        rows_a = conn.execute("""
            SELECT component_b_id as connected_id, connection_type, cable_id
            FROM connections
            WHERE component_a_id = ?
        """, (component_id,)).fetchall()

        # Get connections where component is B
        rows_b = conn.execute("""
            SELECT component_a_id as connected_id, connection_type, cable_id
            FROM connections
            WHERE component_b_id = ?
        """, (component_id,)).fetchall()

        return [dict(row) for row in rows_a] + [dict(row) for row in rows_b]


def remove_connection(connection_id: int, db: Optional[Database] = None):
    """Remove a connection by its ID"""
    if db is None:
        db = get_default_db()

    with db.get_connection() as conn:
        conn.execute("DELETE FROM connections WHERE id = ?", (connection_id,))
        conn.commit()


def add_maintenance_log(component_id: str, description: str,
                       log_type: str = 'note',
                       severity: str = 'info',
                       logged_by: Optional[str] = None,
                       resolution: Optional[str] = None,
                       image_path: Optional[str] = None,
                       db: Optional[Database] = None) -> int:
    """
    Add a maintenance log entry for a component

    Args:
        component_id: ID of component
        description: Log description/comment
        log_type: Type of log ('issue', 'repair', 'maintenance', 'note')
        severity: Severity level ('critical', 'warning', 'info')
        logged_by: Who created the log entry
        resolution: Resolution text (optional)
        image_path: Relative path to attached image (optional)
        db: Database instance

    Returns:
        log_id: ID of created log entry
    """
    if db is None:
        db = get_default_db()

    # Verify component exists
    component = Component.get(component_id, db)
    if not component:
        raise ValueError(f"Component {component_id} not found")

    # Validate log_type and severity
    valid_log_types = ['issue', 'repair', 'maintenance', 'note']
    valid_severities = ['critical', 'warning', 'info']

    if log_type not in valid_log_types:
        raise ValueError(f"Invalid log_type: {log_type}. Must be one of {valid_log_types}")
    if severity not in valid_severities:
        raise ValueError(f"Invalid severity: {severity}. Must be one of {valid_severities}")

    with db.get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO maintenance_log
            (component_id, log_date, log_type, severity, description,
             resolution, logged_by, image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (component_id, datetime.now().isoformat(), log_type, severity,
              description, resolution, logged_by, image_path))

        conn.commit()
        return cursor.lastrowid


def get_maintenance_logs(component_id: str,
                        db: Optional[Database] = None) -> List[Dict[str, Any]]:
    """
    Get all maintenance logs for a component

    Returns list of log entries ordered by date (newest first)
    """
    if db is None:
        db = get_default_db()

    with db.get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM maintenance_log
            WHERE component_id = ?
            ORDER BY log_date DESC
        """, (component_id,)).fetchall()

        return [dict(row) for row in rows]


def assemble_module(module_id: str,
                   sensor_id: Optional[str] = None,
                   hybrid_id: Optional[str] = None,
                   notes: Optional[str] = None,
                   assembled_by: Optional[str] = None,
                   db: Optional[Database] = None):
    """
    Assemble a sensor and/or hybrid onto a module

    Args:
        module_id: ID of the module component
        sensor_id: ID of sensor to assemble (optional)
        hybrid_id: ID of hybrid to assemble (optional)
        notes: Assembly notes/comments
        assembled_by: Who performed the assembly
        db: Database instance

    Raises:
        ValueError: If module doesn't exist, is not a module type, or components already assembled
    """
    if db is None:
        db = get_default_db()

    # Get module
    module = Component.get(module_id, db)
    if not module:
        raise ValueError(f"Module {module_id} not found")
    if module.type != 'module':
        raise ValueError(f"Component {module_id} is not a module (type: {module.type})")

    # Verify sensor if provided
    if sensor_id:
        sensor = Component.get(sensor_id, db)
        if not sensor:
            raise ValueError(f"Sensor {sensor_id} not found")
        if sensor.type != 'sensor':
            raise ValueError(f"Component {sensor_id} is not a sensor (type: {sensor.type})")

        # Check if sensor is already assembled on another module
        with db.get_connection() as conn:
            existing = conn.execute("""
                SELECT id FROM components
                WHERE assembled_sensor_id = ? AND id != ?
            """, (sensor_id, module_id)).fetchone()
            if existing:
                raise ValueError(f"Sensor {sensor_id} is already assembled on module {existing['id']}")

        # Update module with sensor
        module.assembled_sensor_id = sensor_id

    # Verify hybrid if provided
    if hybrid_id:
        hybrid = Component.get(hybrid_id, db)
        if not hybrid:
            raise ValueError(f"Hybrid {hybrid_id} not found")
        if hybrid.type != 'hybrid':
            raise ValueError(f"Component {hybrid_id} is not a hybrid (type: {hybrid.type})")

        # Check if hybrid is already assembled on another module
        with db.get_connection() as conn:
            existing = conn.execute("""
                SELECT id FROM components
                WHERE assembled_hybrid_id = ? AND id != ?
            """, (hybrid_id, module_id)).fetchone()
            if existing:
                raise ValueError(f"Hybrid {hybrid_id} is already assembled on module {existing['id']}")

        # Update module with hybrid
        module.assembled_hybrid_id = hybrid_id

    # Save module
    module.save(db)

    # Add maintenance log if notes provided
    if notes:
        log_description = f"Assembly: "
        parts = []
        if sensor_id:
            parts.append(f"sensor {sensor_id}")
        if hybrid_id:
            parts.append(f"hybrid {hybrid_id}")
        log_description += " and ".join(parts) + f" - {notes}"

        add_maintenance_log(
            module_id,
            log_description,
            log_type='maintenance',
            severity='info',
            logged_by=assembled_by,
            db=db
        )


def disassemble_module(module_id: str,
                      notes: Optional[str] = None,
                      disassembled_by: Optional[str] = None,
                      db: Optional[Database] = None):
    """
    Disassemble a module (remove sensor and hybrid)

    Args:
        module_id: ID of the module component
        notes: Disassembly notes/comments
        disassembled_by: Who performed the disassembly
        db: Database instance

    Raises:
        ValueError: If module doesn't exist or is not a module type
    """
    if db is None:
        db = get_default_db()

    # Get module
    module = Component.get(module_id, db)
    if not module:
        raise ValueError(f"Module {module_id} not found")
    if module.type != 'module':
        raise ValueError(f"Component {module_id} is not a module (type: {module.type})")

    # Check if anything is assembled
    if not module.assembled_sensor_id and not module.assembled_hybrid_id:
        raise ValueError(f"Module {module_id} has nothing assembled")

    # Record what was disassembled
    disassembled_parts = []
    if module.assembled_sensor_id:
        disassembled_parts.append(f"sensor {module.assembled_sensor_id}")
    if module.assembled_hybrid_id:
        disassembled_parts.append(f"hybrid {module.assembled_hybrid_id}")

    # Clear assembly
    module.assembled_sensor_id = None
    module.assembled_hybrid_id = None
    module.save(db)

    # Add maintenance log
    log_description = f"Disassembly: removed " + " and ".join(disassembled_parts)
    if notes:
        log_description += f" - {notes}"

    add_maintenance_log(
        module_id,
        log_description,
        log_type='maintenance',
        severity='info',
        logged_by=disassembled_by,
        db=db
    )


def get_component_images(component_id: str,
                         db: Optional[Database] = None) -> List[Dict[str, Any]]:
    """
    Get all images for a component

    Args:
        component_id: ID of the component
        db: Database instance

    Returns:
        List of image records ordered by upload date (newest first)
    """
    if db is None:
        db = get_default_db()

    with db.get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM component_images
            WHERE component_id = ?
            ORDER BY upload_date DESC
        """, (component_id,)).fetchall()

        return [dict(row) for row in rows]

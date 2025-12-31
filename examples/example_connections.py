#!/usr/bin/env python3
"""
Example: Working with connections between components

This demonstrates how to:
1. Create connections between components (e.g., FEB to module)
2. Query connections
3. Track cables used in connections
"""

from hps_svt_tracker import Component, get_default_db
from datetime import datetime


def create_connection(component_a_id: str, component_b_id: str,
                     connection_type: str = None,
                     cable_id: str = None,
                     notes: str = None,
                     db=None):
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


def get_connections_for_component(component_id: str, db=None):
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


def get_connected_components(component_id: str, db=None):
    """
    Get all components connected to a given component

    Returns:
        List of (connected_component_id, connection_type, cable_id) tuples
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


def main():
    """Example usage"""
    db = get_default_db()

    print("="*60)
    print("Connection Management Example")
    print("="*60)

    # 1. Create components if they don't exist
    print("\n1. Creating components...")

    # Create a module
    module = Component.get('HPK-SN999', db)
    if not module:
        module = Component(
            id='HPK-SN999',
            type='module',
            manufacturer='Hamamatsu',
            installation_status='qualified',
            current_location='Clean Room'
        )
        module.save(db)
        print(f"   Created module: {module.id}")
    else:
        print(f"   Module {module.id} already exists")

    # Create a FEB
    feb = Component.get('FEB-100', db)
    if not feb:
        feb = Component(
            id='FEB-100',
            type='feb',
            serial_number='FEB-100-2024',
            manufacturer='SLAC',
            installation_status='spare',
            current_location='Electronics Lab'
        )
        feb.save(db)
        print(f"   Created FEB: {feb.id}")
    else:
        print(f"   FEB {feb.id} already exists")

    # Create a cable
    cable = Component.get('CABLE-SIG-42', db)
    if not cable:
        cable = Component(
            id='CABLE-SIG-42',
            type='cable',
            manufacturer='Generic',
            installation_status='spare',
            current_location='Electronics Lab',
            attributes={'length_cm': 50, 'cable_type': 'signal'}
        )
        cable.save(db)
        print(f"   Created cable: {cable.id}")
    else:
        print(f"   Cable {cable.id} already exists")

    # 2. Create a connection from FEB to module via cable
    print("\n2. Creating connection: FEB-100 -> CABLE-SIG-42 -> HPK-SN999")

    connection_id = create_connection(
        component_a_id='FEB-100',
        component_b_id='HPK-SN999',
        connection_type='signal',
        cable_id='CABLE-SIG-42',
        notes='Connected for Layer1_top_axial readout',
        db=db
    )
    print(f"   Created connection (ID: {connection_id})")

    # 3. Query connections
    print("\n3. Querying connections for FEB-100...")
    feb_connections = get_connections_for_component('FEB-100', db)
    print(f"   Found {len(feb_connections)} connections:")
    for conn in feb_connections:
        print(f"      {conn['component_a_id']} <-> {conn['component_b_id']}")
        print(f"         Type: {conn['connection_type']}")
        print(f"         Cable: {conn['cable_id']}")
        print(f"         Date: {conn['installation_date'][:19]}")

    # 4. Get all components connected to the module
    print("\n4. Finding all components connected to HPK-SN999...")
    connected = get_connected_components('HPK-SN999', db)
    print(f"   Found {len(connected)} connected components:")
    for c in connected:
        print(f"      {c['connected_id']} via {c['cable_id'] or 'direct'} ({c['connection_type']})")

    # 5. Show connection details using JOIN
    print("\n5. Connection details with component info:")
    with db.get_connection() as conn:
        rows = conn.execute("""
            SELECT
                c.id,
                c.component_a_id,
                a.type as a_type,
                c.component_b_id,
                b.type as b_type,
                c.connection_type,
                c.cable_id,
                c.notes
            FROM connections c
            JOIN components a ON c.component_a_id = a.id
            JOIN components b ON c.component_b_id = b.id
            ORDER BY c.installation_date DESC
            LIMIT 10
        """).fetchall()

        for row in rows:
            print(f"\n   Connection #{row['id']}:")
            print(f"      {row['component_a_id']} ({row['a_type']}) <-> {row['component_b_id']} ({row['b_type']})")
            print(f"      Type: {row['connection_type']}, Cable: {row['cable_id']}")
            if row['notes']:
                print(f"      Notes: {row['notes']}")

    print("\n" + "="*60)
    print("Example completed!")
    print("="*60)


if __name__ == '__main__':
    main()

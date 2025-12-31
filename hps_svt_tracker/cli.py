"""
Command-line interface for HPS SVT Component Tracker
"""
import click
import json
import getpass
from datetime import datetime
from tabulate import tabulate

from .database import get_default_db, Database
from .models import (
    Component, TestResult,
    install_component, remove_component,
    create_connection, get_connections_for_component,
    get_connected_components, remove_connection,
    add_maintenance_log, get_maintenance_logs
)


def get_current_user():
    """Get the current username"""
    try:
        return getpass.getuser()
    except Exception:
        # Fallback if getpass fails
        import os
        return os.environ.get('USER') or os.environ.get('USERNAME') or 'unknown'


@click.group()
@click.option('--db-path', default=None, help='Path to database file')
@click.pass_context
def cli(ctx, db_path):
    """HPS SVT Component Tracker - Manage detector components and tests"""
    ctx.ensure_object(dict)
    ctx.obj['db'] = Database(db_path) if db_path else get_default_db()


@cli.command()
@click.pass_context
def init(ctx):
    """Initialize the database"""
    db = ctx.obj['db']
    db.initialize_schema()
    click.echo(f"Database initialized at: {db.db_path}")
    click.echo(f"Test data directory: {db.data_dir}")


@cli.command()
@click.option('--id', 'component_id', required=True, help='Component ID')
@click.option('--type', 'component_type', required=True, 
              type=click.Choice(Component.TYPES), help='Component type')
@click.option('--serial', help='Serial number (if different from ID)')
@click.option('--manufacturer', help='Manufacturer name')
@click.option('--location', default='Incoming', help='Current location')
@click.option('--status', default='incoming', 
              type=click.Choice(Component.STATUSES), help='Installation status')
@click.option('--notes', help='Additional notes')
@click.pass_context
def add(ctx, component_id, component_type, serial, manufacturer, location, status, notes):
    """Add a new component to the database"""
    db = ctx.obj['db']
    
    # Check if component already exists
    existing = Component.get(component_id, db)
    if existing:
        click.echo(f"Error: Component {component_id} already exists", err=True)
        return
    
    component = Component(
        id=component_id,
        type=component_type,
        serial_number=serial,
        manufacturer=manufacturer,
        current_location=location,
        installation_status=status,
        notes=notes
    )
    
    component.save(db)
    click.echo(f"Added component: {component_id}")


@cli.command()
@click.option('--type', 'component_type', help='Filter by type')
@click.option('--status', help='Filter by status')
@click.option('--position', help='Filter by installed position')
@click.pass_context
def list(ctx, component_type, status, position):
    """List components"""
    db = ctx.obj['db']
    
    # Get components
    components = Component.list_all(component_type=component_type, status=status, db=db)
    
    # Filter by position if specified
    if position:
        components = [c for c in components if c.installed_position == position]
    
    if not components:
        click.echo("No components found")
        return
    
    # Format for display
    table_data = []
    for c in components:
        table_data.append([
            c.id,
            c.type,
            c.installation_status,
            c.installed_position or '',
            c.current_location or '',
        ])
    
    headers = ['ID', 'Type', 'Status', 'Position', 'Location']
    click.echo(tabulate(table_data, headers=headers, tablefmt='simple'))
    click.echo(f"\nTotal: {len(components)} components")


@cli.command()
@click.argument('component_id')
@click.pass_context
def show(ctx, component_id):
    """Show detailed information about a component"""
    db = ctx.obj['db']
    
    component = Component.get(component_id, db)
    if not component:
        click.echo(f"Component {component_id} not found", err=True)
        return
    
    # Component details
    click.echo(f"\n{'='*60}")
    click.echo(f"Component: {component.id}")
    click.echo(f"{'='*60}")
    click.echo(f"Type:              {component.type}")
    click.echo(f"Serial Number:     {component.serial_number}")
    click.echo(f"Manufacturer:      {component.manufacturer or 'N/A'}")
    click.echo(f"Status:            {component.installation_status}")
    click.echo(f"Current Location:  {component.current_location or 'N/A'}")
    click.echo(f"Installed Position: {component.installed_position or 'N/A'}")
    
    if component.attributes:
        click.echo(f"\nAttributes:")
        for key, value in component.attributes.items():
            click.echo(f"  {key}: {value}")
    
    if component.notes:
        click.echo(f"\nNotes: {component.notes}")
    
    # Get test history
    test_results = TestResult.get_for_component(component_id, db)
    if test_results:
        click.echo(f"\n{'='*60}")
        click.echo(f"Test History ({len(test_results)} tests)")
        click.echo(f"{'='*60}")
        
        table_data = []
        for test in test_results:
            table_data.append([
                test['test_date'][:19],  # Trim microseconds
                test['test_type'],
                'PASS' if test['pass_fail'] else 'FAIL' if test['pass_fail'] is not None else 'N/A',
                test['tested_by'] or ''
            ])
        
        headers = ['Date', 'Test Type', 'Result', 'Tested By']
        click.echo(tabulate(table_data, headers=headers, tablefmt='simple'))
    else:
        click.echo(f"\nNo test history")
    
    # Get installation history
    with db.get_connection() as conn:
        installations = conn.execute("""
            SELECT * FROM installation_history 
            WHERE component_id = ? 
            ORDER BY installation_date DESC
        """, (component_id,)).fetchall()
    
    if installations:
        click.echo(f"\n{'='*60}")
        click.echo(f"Installation History ({len(installations)} installations)")
        click.echo(f"{'='*60}")
        
        table_data = []
        for inst in installations:
            install_date = inst['installation_date'][:19]
            removal_date = inst['removal_date'][:19] if inst['removal_date'] else 'Current'
            table_data.append([
                inst['position'],
                install_date,
                removal_date,
                inst['run_period'] or ''
            ])
        
        headers = ['Position', 'Installed', 'Removed', 'Run Period']
        click.echo(tabulate(table_data, headers=headers, tablefmt='simple'))

    # Get maintenance logs
    logs = get_maintenance_logs(component_id, db)
    if logs:
        click.echo(f"\n{'='*60}")
        click.echo(f"Maintenance Log ({len(logs)} entries)")
        click.echo(f"{'='*60}")

        table_data = []
        for log in logs:
            log_date = log['log_date'][:19]
            table_data.append([
                log_date,
                log['log_type'],
                log['severity'],
                log['description'][:50] + '...' if len(log['description']) > 50 else log['description'],
                log['logged_by'] or ''
            ])

        headers = ['Date', 'Type', 'Severity', 'Description', 'Logged By']
        click.echo(tabulate(table_data, headers=headers, tablefmt='simple'))


@cli.command()
@click.argument('component_id')
@click.option('--type', 'test_type', required=True, help='Test type')
@click.option('--pass', 'test_pass', is_flag=True, help='Test passed')
@click.option('--fail', 'test_fail', is_flag=True, help='Test failed')
@click.option('--voltage', type=float, help='Voltage measurement')
@click.option('--current', type=float, help='Current measurement')
@click.option('--noise', type=float, help='Noise level')
@click.option('--temp', type=float, help='Temperature')
@click.option('--images', multiple=True, help='Image file paths')
@click.option('--data-file', help='Data file path')
@click.option('--tested-by', default=None, help='Who performed the test (defaults to current user)')
@click.option('--notes', help='Test notes')
@click.pass_context
def test(ctx, component_id, test_type, test_pass, test_fail, voltage,
         current, noise, temp, images, data_file, tested_by, notes):
    """Record a test result for a component"""
    db = ctx.obj['db']

    # Verify component exists
    component = Component.get(component_id, db)
    if not component:
        click.echo(f"Component {component_id} not found", err=True)
        return

    # Use current user if not specified
    if tested_by is None:
        tested_by = get_current_user()

    # Determine pass/fail
    pass_fail = None
    if test_pass:
        pass_fail = True
    elif test_fail:
        pass_fail = False

    # Build measurements dict
    measurements = {}
    if voltage is not None:
        measurements['voltage_measured'] = voltage
    if current is not None:
        measurements['current_measured'] = current
    if noise is not None:
        measurements['noise_level'] = noise
    if temp is not None:
        measurements['temperature'] = temp

    # Create test result
    test_result = TestResult(
        component_id=component_id,
        test_type=test_type,
        pass_fail=pass_fail,
        measurements=measurements,
        image_files=list(images) if images else None,
        data_file=data_file,
        tested_by=tested_by,
        notes=notes
    )

    test_id = test_result.save(db)
    click.echo(f"Test result recorded (ID: {test_id})")

    if test_result.stored_image_paths:
        click.echo(f"Stored {len(test_result.stored_image_paths)} images")
    if test_result.stored_data_path:
        click.echo(f"Stored data file: {test_result.stored_data_path}")


@cli.command()
@click.argument('component_id')
@click.argument('position')
@click.option('--run-period', required=True, help='Run period name')
@click.option('--installed-by', default=None, help='Who installed it (defaults to current user)')
@click.option('--notes', help='Installation notes')
@click.pass_context
def install(ctx, component_id, position, run_period, installed_by, notes):
    """Install a component at a specific position"""
    db = ctx.obj['db']

    # Use current user if not specified
    if installed_by is None:
        installed_by = get_current_user()

    try:
        install_component(component_id, position, run_period,
                         installed_by=installed_by, notes=notes, db=db)
        click.echo(f"Installed {component_id} at position {position}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)


@cli.command()
@click.argument('component_id')
@click.option('--reason', required=True, help='Removal reason')
@click.option('--removed-by', default=None, help='Who removed it (defaults to current user)')
@click.option('--location', default='Storage', help='New location')
@click.pass_context
def remove(ctx, component_id, reason, removed_by, location):
    """Remove a component from its installed position"""
    db = ctx.obj['db']

    # Use current user if not specified
    if removed_by is None:
        removed_by = get_current_user()

    try:
        remove_component(component_id, reason,
                        removed_by=removed_by,
                        new_location=location, db=db)
        click.echo(f"Removed {component_id}, now at {location}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)


@cli.command()
@click.pass_context
def summary(ctx):
    """Show summary statistics"""
    db = ctx.obj['db']
    
    with db.get_connection() as conn:
        # Component counts by type
        click.echo("\n=== Components by Type ===")
        rows = conn.execute("""
            SELECT type, COUNT(*) as count 
            FROM components 
            GROUP BY type 
            ORDER BY type
        """).fetchall()
        
        if rows:
            table_data = [[row['type'], row['count']] for row in rows]
            click.echo(tabulate(table_data, headers=['Type', 'Count'], tablefmt='simple'))
        
        # Component counts by status
        click.echo("\n=== Components by Status ===")
        rows = conn.execute("""
            SELECT installation_status, COUNT(*) as count 
            FROM components 
            GROUP BY installation_status 
            ORDER BY installation_status
        """).fetchall()
        
        if rows:
            table_data = [[row['installation_status'], row['count']] for row in rows]
            click.echo(tabulate(table_data, headers=['Status', 'Count'], tablefmt='simple'))
        
        # Recent tests
        click.echo("\n=== Recent Tests (Last 30 days) ===")
        recent_tests = TestResult.get_recent(days=30, db=db)
        click.echo(f"Total tests: {len(recent_tests)}")

        if recent_tests:
            # Count by test type
            test_types = {}
            for test in recent_tests:
                tt = test['test_type']
                test_types[tt] = test_types.get(tt, 0) + 1

            table_data = [[tt, count] for tt, count in sorted(test_types.items())]
            click.echo(tabulate(table_data, headers=['Test Type', 'Count'], tablefmt='simple'))

        # Connections
        click.echo("\n=== Connections ===")
        total_connections = conn.execute(
            "SELECT COUNT(*) as count FROM connections"
        ).fetchone()['count']
        click.echo(f"Total connections: {total_connections}")

        if total_connections > 0:
            # Count by connection type
            conn_type_rows = conn.execute("""
                SELECT connection_type, COUNT(*) as count
                FROM connections
                GROUP BY connection_type
                ORDER BY count DESC
            """).fetchall()

            if conn_type_rows:
                table_data = []
                for row in conn_type_rows:
                    conn_type = row['connection_type'] or '(no type)'
                    table_data.append([conn_type, row['count']])
                click.echo(tabulate(table_data, headers=['Connection Type', 'Count'], tablefmt='simple'))

                # Show actual connections for each type
                click.echo("\nConnection Details:")
                for row in conn_type_rows:
                    conn_type = row['connection_type'] or '(no type)'
                    click.echo(f"\n  {conn_type} ({row['count']}):")

                    # Get connections for this type
                    if row['connection_type'] is None:
                        connections = conn.execute("""
                            SELECT component_a_id, component_b_id, cable_id
                            FROM connections
                            WHERE connection_type IS NULL
                            ORDER BY component_a_id
                        """).fetchall()
                    else:
                        connections = conn.execute("""
                            SELECT component_a_id, component_b_id, cable_id
                            FROM connections
                            WHERE connection_type = ?
                            ORDER BY component_a_id
                        """, (row['connection_type'],)).fetchall()

                    for c in connections:
                        cable_info = f" (via {c['cable_id']})" if c['cable_id'] else ""
                        click.echo(f"    - {c['component_a_id']} <-> {c['component_b_id']}{cable_info}")


@cli.command()
@click.argument('component_a_id')
@click.argument('component_b_id')
@click.option('--type', 'connection_type', help='Connection type (signal, power, optical, etc.)')
@click.option('--cable', 'cable_id', help='Cable component ID used for connection')
@click.option('--notes', help='Connection notes')
@click.pass_context
def connect(ctx, component_a_id, component_b_id, connection_type, cable_id, notes):
    """Create a connection between two components"""
    db = ctx.obj['db']

    try:
        connection_id = create_connection(
            component_a_id, component_b_id,
            connection_type=connection_type,
            cable_id=cable_id,
            notes=notes,
            db=db
        )
        click.echo(f"Created connection (ID: {connection_id})")
        click.echo(f"  {component_a_id} <-> {component_b_id}")
        if cable_id:
            click.echo(f"  via cable: {cable_id}")
        if connection_type:
            click.echo(f"  type: {connection_type}")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)


@cli.command()
@click.argument('component_id')
@click.pass_context
def connections(ctx, component_id):
    """Show all connections for a component"""
    db = ctx.obj['db']

    # Verify component exists
    component = Component.get(component_id, db)
    if not component:
        click.echo(f"Component {component_id} not found", err=True)
        return

    # Get connections
    conns = get_connections_for_component(component_id, db)

    if not conns:
        click.echo(f"No connections found for {component_id}")
        return

    click.echo(f"\n{'='*60}")
    click.echo(f"Connections for {component_id}")
    click.echo(f"{'='*60}")

    table_data = []
    for conn in conns:
        # Determine the "other" component
        if conn['component_a_id'] == component_id:
            other = conn['component_b_id']
        else:
            other = conn['component_a_id']

        table_data.append([
            conn['id'],
            f"{conn['component_a_id']} <-> {conn['component_b_id']}",
            conn['connection_type'] or '',
            conn['cable_id'] or '',
            conn['installation_date'][:19] if conn['installation_date'] else ''
        ])

    headers = ['ID', 'Connection', 'Type', 'Cable', 'Date']
    click.echo(tabulate(table_data, headers=headers, tablefmt='simple'))
    click.echo(f"\nTotal: {len(conns)} connections")


@cli.command()
@click.argument('connection_id', type=int)
@click.pass_context
def disconnect(ctx, connection_id):
    """Remove a connection by its ID"""
    db = ctx.obj['db']

    # Get connection details first
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM connections WHERE id = ?", (connection_id,)
        ).fetchone()

        if not row:
            click.echo(f"Connection {connection_id} not found", err=True)
            return

        click.echo(f"Removing connection: {row['component_a_id']} <-> {row['component_b_id']}")

    try:
        remove_connection(connection_id, db)
        click.echo(f"Connection {connection_id} removed")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@cli.command()
@click.argument('component_id')
@click.argument('description')
@click.option('--type', 'log_type',
              type=click.Choice(['issue', 'repair', 'maintenance', 'note']),
              default='note', help='Log type')
@click.option('--severity',
              type=click.Choice(['critical', 'warning', 'info']),
              default='info', help='Severity level')
@click.option('--logged-by', default=None, help='Who created this log entry (defaults to current user)')
@click.option('--resolution', help='Resolution description (for issues/repairs)')
@click.pass_context
def log(ctx, component_id, description, log_type, severity, logged_by, resolution):
    """Add a maintenance log entry for a component"""
    db = ctx.obj['db']

    # Use current user if not specified
    if logged_by is None:
        logged_by = get_current_user()

    try:
        log_id = add_maintenance_log(
            component_id, description,
            log_type=log_type,
            severity=severity,
            logged_by=logged_by,
            resolution=resolution,
            db=db
        )
        click.echo(f"Log entry created (ID: {log_id})")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)


@cli.command()
@click.argument('component_id')
@click.argument('description')
@click.option('--logged-by', default=None, help='Who created this comment (defaults to current user)')
@click.pass_context
def comment(ctx, component_id, description, logged_by):
    """Add a comment for a component (alias for 'log' with type=note)"""
    db = ctx.obj['db']

    # Use current user if not specified
    if logged_by is None:
        logged_by = get_current_user()

    try:
        log_id = add_maintenance_log(
            component_id, description,
            log_type='note',
            severity='info',
            logged_by=logged_by,
            db=db
        )
        click.echo(f"Comment added (ID: {log_id})")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)


if __name__ == '__main__':
    cli()

"""
Component routes for HPS SVT Tracker web interface
Handles component listing and detail views
"""
from flask import Blueprint, render_template, request, g, abort
from hps_svt_tracker.models import Component, TestResult, get_maintenance_logs, get_connections_for_component


components_bp = Blueprint('components', __name__)


@components_bp.route('/')
def list_components():
    """List all components with filters"""

    # Get filter parameters from query string
    component_type = request.args.get('type')
    status = request.args.get('status')
    page = request.args.get('page', 1, type=int)

    # Use existing model method to get components
    components = Component.list_all(
        component_type=component_type,
        status=status,
        db=g.db
    )

    # Simple pagination (slice the list)
    per_page = 50
    start = (page - 1) * per_page
    end = start + per_page
    total = len(components)
    components_page = components[start:end]

    # Get available types and statuses for filter dropdowns
    component_types = Component.TYPES
    statuses = Component.STATUSES

    return render_template('components/list.html',
                         components=components_page,
                         total=total,
                         page=page,
                         per_page=per_page,
                         filter_type=component_type,
                         filter_status=status,
                         component_types=component_types,
                         statuses=statuses)


@components_bp.route('/<component_id>')
def component_detail(component_id):
    """Show detailed information for a specific component"""

    # Get the component
    component = Component.get(component_id, g.db)
    if not component:
        abort(404, description=f"Component '{component_id}' not found")

    # Get related data using existing model methods
    tests = TestResult.get_for_component(component_id, g.db)
    logs = get_maintenance_logs(component_id, g.db)
    connections = get_connections_for_component(component_id, g.db)

    # Get installation history
    with g.db.get_connection() as conn:
        installations = conn.execute("""
            SELECT *
            FROM installation_history
            WHERE component_id = ?
            ORDER BY installation_date DESC
        """, (component_id,)).fetchall()

    # Check if this component is used in any module assembly
    assembly_info = None
    if component.type in ['sensor', 'hybrid']:
        with g.db.get_connection() as conn:
            if component.type == 'sensor':
                assembly_info = conn.execute("""
                    SELECT id, type FROM components WHERE assembled_sensor_id = ?
                """, (component_id,)).fetchone()
            else:  # hybrid
                assembly_info = conn.execute("""
                    SELECT id, type FROM components WHERE assembled_hybrid_id = ?
                """, (component_id,)).fetchone()

    return render_template('components/detail.html',
                         component=component,
                         tests=tests,
                         logs=logs,
                         connections=connections,
                         installations=installations,
                         assembly_info=assembly_info)

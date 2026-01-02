"""
Main routes for HPS SVT Tracker web interface
Includes homepage, dashboard, and general pages
"""
from flask import Blueprint, render_template, g
from hps_svt_tracker.models import TestResult


main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Homepage/Dashboard with statistics and recent activity"""

    # Get statistics
    with g.db.get_connection() as conn:
        stats = {
            'total_components': conn.execute(
                "SELECT COUNT(*) as count FROM components"
            ).fetchone()['count'],

            'installed': conn.execute(
                "SELECT COUNT(*) as count FROM components WHERE installation_status='installed'"
            ).fetchone()['count'],

            'spare': conn.execute(
                "SELECT COUNT(*) as count FROM components WHERE installation_status='spare'"
            ).fetchone()['count'],

            'testing': conn.execute(
                "SELECT COUNT(*) as count FROM components WHERE installation_status='testing'"
            ).fetchone()['count'],

            'recent_tests': conn.execute(
                "SELECT COUNT(*) as count FROM test_results WHERE test_date > date('now', '-30 days')"
            ).fetchone()['count']
        }

        # Get component counts by type
        component_counts = conn.execute("""
            SELECT type, COUNT(*) as count
            FROM components
            GROUP BY type
            ORDER BY count DESC
        """).fetchall()

    # Get recent tests (last 10)
    recent_tests = TestResult.get_recent(days=30, db=g.db)[:10]

    return render_template('index.html',
                         stats=stats,
                         component_counts=component_counts,
                         recent_tests=recent_tests)

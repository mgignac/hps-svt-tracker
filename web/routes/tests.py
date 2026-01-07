"""
Test result routes for HPS SVT Tracker web interface
Handles test result detail views
"""
from flask import Blueprint, render_template, g, abort, request, redirect, url_for, flash
import json
from hps_svt_tracker.models import TestResult


tests_bp = Blueprint('tests', __name__)


@tests_bp.route('/<int:test_id>')
def test_detail(test_id):
    """Show detailed information for a specific test result"""

    # Get the test result
    test = TestResult.get_by_id(test_id, g.db)
    if not test:
        abort(404, description=f"Test result #{test_id} not found")

    # Get files organized by type
    files_by_type = TestResult.get_files_by_type(test_id, db=g.db)

    # Parse metadata_json for each file
    for file_type, files in files_by_type.items():
        for f in files:
            if f.get('metadata_json'):
                try:
                    f['metadata_json'] = json.loads(f['metadata_json'])
                except (json.JSONDecodeError, TypeError):
                    f['metadata_json'] = {}
            else:
                f['metadata_json'] = {}

    # Parse measurements JSON if it exists
    measurements_dict = {}
    if test.get('measurements_json'):
        try:
            measurements_dict = json.loads(test['measurements_json'])
        except (json.JSONDecodeError, TypeError):
            measurements_dict = {}

    return render_template('tests/detail.html',
                         test=test,
                         files_by_type=files_by_type,
                         measurements_dict=measurements_dict)


@tests_bp.route('/<int:test_id>/update-result', methods=['POST'])
def update_result(test_id):
    """Update the pass/fail result of a test"""
    # Get the test result to verify it exists
    test = TestResult.get_by_id(test_id, g.db)
    if not test:
        abort(404, description=f"Test result #{test_id} not found")

    # Get the new result value from the form
    result = request.form.get('result')

    # Convert to boolean or None
    if result == 'pass':
        pass_fail = True
    elif result == 'fail':
        pass_fail = False
    else:  # 'na' or anything else
        pass_fail = None

    # Update the database
    with g.db.get_connection() as conn:
        conn.execute(
            "UPDATE test_results SET pass_fail = ? WHERE id = ?",
            [pass_fail, test_id]
        )
        conn.commit()

    flash(f"Test result updated successfully", "success")
    return redirect(url_for('tests.test_detail', test_id=test_id))


@tests_bp.route('/<int:test_id>/delete', methods=['POST'])
def delete_test(test_id):
    """Delete a test result and its associated files"""
    # Get the test result to verify it exists and get component_id for redirect
    test = TestResult.get_by_id(test_id, g.db)
    if not test:
        abort(404, description=f"Test result #{test_id} not found")

    component_id = test['component_id']

    # Delete associated files from database (actual files remain on disk)
    with g.db.get_connection() as conn:
        # Delete test files records
        conn.execute("DELETE FROM test_files WHERE test_id = ?", [test_id])
        # Delete the test result
        conn.execute("DELETE FROM test_results WHERE id = ?", [test_id])
        conn.commit()

    flash(f"Test #{test_id} deleted successfully", "success")
    return redirect(url_for('components.component_detail', component_id=component_id))

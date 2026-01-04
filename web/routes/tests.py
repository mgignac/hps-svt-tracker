"""
Test result routes for HPS SVT Tracker web interface
Handles test result detail views
"""
from flask import Blueprint, render_template, g, abort
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

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

    # Parse JSON fields if they exist
    image_paths = []
    if test.image_paths:
        try:
            image_paths = json.loads(test.image_paths)
        except (json.JSONDecodeError, TypeError):
            image_paths = []

    measurements_dict = {}
    if test.measurements:
        try:
            measurements_dict = json.loads(test.measurements)
        except (json.JSONDecodeError, TypeError):
            measurements_dict = {}

    return render_template('tests/detail.html',
                         test=test,
                         image_paths=image_paths,
                         measurements_dict=measurements_dict)

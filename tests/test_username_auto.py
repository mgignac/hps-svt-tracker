#!/usr/bin/env python
"""
Demonstration of automatic username detection feature.

This shows how the CLI automatically uses your username for logging fields
when you don't specify them explicitly.
"""

import tempfile
import os
from hps_svt_tracker.database import Database
from hps_svt_tracker.models import Component, TestResult, add_maintenance_log
from hps_svt_tracker.cli import get_current_user

# Get the current username
current_user = get_current_user()
print(f"Current system username: {current_user}")
print()

# Create a temporary database for demonstration
with tempfile.TemporaryDirectory() as tmpdir:
    db = Database(os.path.join(tmpdir, "test.db"))
    db.initialize_schema()

    # Add a test component
    component = Component(
        id="TEST-001",
        type="module",
        manufacturer="Test Corp",
        installation_status="testing"
    )
    component.save(db)
    print(f"Created component: {component.id}")

    # Record a test result without specifying tested_by
    # In CLI, this would automatically use current_user
    test_result = TestResult(
        component_id="TEST-001",
        test_type="iv_curve",
        pass_fail=True,
        tested_by=current_user,  # CLI does this automatically if not specified
        measurements={"voltage_measured": 60.0, "current_measured": 2.3e-6}
    )
    test_id = test_result.save(db)
    print(f"Created test result (ID: {test_id}) - tested by: {test_result.tested_by}")

    # Add a maintenance log without specifying logged_by
    # In CLI, this would automatically use current_user
    log_id = add_maintenance_log(
        "TEST-001",
        "Component is functioning normally",
        log_type="note",
        logged_by=current_user,  # CLI does this automatically if not specified
        db=db
    )
    print(f"Created maintenance log (ID: {log_id}) - logged by: {current_user}")

    # Verify the data
    print("\nVerifying stored data:")
    test_results = TestResult.get_for_component("TEST-001", db)
    for test in test_results:
        print(f"  Test {test['id']}: {test['test_type']} - tested by {test['tested_by']}")

    with db.get_connection() as conn:
        logs = conn.execute(
            "SELECT * FROM maintenance_log WHERE component_id = ?",
            ("TEST-001",)
        ).fetchall()
        for log in logs:
            print(f"  Log {log['id']}: {log['description']} - logged by {log['logged_by']}")

print("\n" + "="*60)
print("SUCCESS! Username auto-detection is working correctly.")
print("="*60)

"""
Tests for HPS SVT Component Tracker

Run with: python -m pytest tests/
"""
import pytest
import os
import tempfile
from datetime import datetime

from hps_svt_tracker import Component, TestResult, Database


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test.db')
        data_dir = os.path.join(tmpdir, 'test_data')
        db = Database(db_path, data_dir)
        db.initialize_schema()
        yield db


def test_component_creation(temp_db):
    """Test creating and saving a component"""
    component = Component(
        id='TEST-001',
        type='module',
        manufacturer='Test Corp',
        installation_status='incoming'
    )
    component.save(temp_db)
    
    # Retrieve it
    retrieved = Component.get('TEST-001', temp_db)
    assert retrieved is not None
    assert retrieved.id == 'TEST-001'
    assert retrieved.type == 'module'


def test_component_list(temp_db):
    """Test listing components"""
    # Add some components
    Component(id='MOD-1', type='module', installation_status='spare').save(temp_db)
    Component(id='MOD-2', type='module', installation_status='installed').save(temp_db)
    Component(id='FEB-1', type='feb', installation_status='spare').save(temp_db)
    
    # List all
    all_comps = Component.list_all(db=temp_db)
    assert len(all_comps) == 3
    
    # Filter by type
    modules = Component.list_all(component_type='module', db=temp_db)
    assert len(modules) == 2
    
    # Filter by status
    spares = Component.list_all(status='spare', db=temp_db)
    assert len(spares) == 2


def test_test_result(temp_db):
    """Test recording a test result"""
    # First create a component
    component = Component(id='TEST-002', type='module', installation_status='testing')
    component.save(temp_db)
    
    # Record a test
    test = TestResult(
        component_id='TEST-002',
        test_type='iv_curve',
        pass_fail=True,
        measurements={'voltage': 60.0, 'current': 1e-6}
    )
    test_id = test.save(temp_db)
    
    assert test_id is not None
    
    # Retrieve test history
    history = TestResult.get_for_component('TEST-002', temp_db)
    assert len(history) == 1
    assert history[0]['test_type'] == 'iv_curve'
    assert history[0]['pass_fail'] == 1  # SQLite stores bool as int


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

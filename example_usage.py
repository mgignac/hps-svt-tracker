#!/usr/bin/env python3
"""
Example usage of HPS SVT Component Tracker

This script demonstrates the basic workflow of:
1. Adding components
2. Recording tests
3. Installing components
4. Querying the database
"""

from hps_svt_tracker import Component, TestResult, install_component, get_default_db
import json

def main():
    # Get database connection
    db = get_default_db()
    
    print("="*60)
    print("HPS SVT Component Tracker - Example Usage")
    print("="*60)
    
    # 1. Add a module
    print("\n1. Adding a new module...")
    module = Component(
        id='HPK-SN123456',
        type='module',
        serial_number='HPK-SN123456',
        manufacturer='Hamamatsu',
        installation_status='incoming',
        current_location='Receiving',
        attributes={
            'hybrid_serial': 'HYB-001',
            'sensor_serial': 'SENS-789',
            'apv25_chips': ['APV-A1', 'APV-A2', 'APV-A3', 'APV-A4'],
            'channel_count': 512
        },
        notes='New module for 2025 spring run'
    )
    module.save(db)
    print(f"   Added module: {module.id}")
    
    # 2. Record an IV curve test
    print("\n2. Recording IV curve test...")
    iv_test = TestResult(
        component_id='HPK-SN123456',
        test_type='iv_curve',
        pass_fail=True,
        measurements={
            'voltage_measured': 60.0,
            'current_measured': 2.3e-6,
            'temperature': -9.0,
            'depletion_voltage': 30.0
        },
        tested_by='Jane Doe',
        test_setup='Test Bench 2',
        notes='Normal operation, meets specifications'
    )
    test_id = iv_test.save(db)
    print(f"   Recorded test (ID: {test_id})")
    
    # 3. Record a noise test
    print("\n3. Recording noise calibration test...")
    noise_test = TestResult(
        component_id='HPK-SN123456',
        test_type='noise_calibration',
        pass_fail=True,
        measurements={
            'mean_noise': 1600,  # electrons
            'max_noise': 2100,
            'bad_channels': [47, 128, 203],
            'threshold_setting': 3.0  # sigma
        },
        tested_by='Jane Doe',
        notes='Within specifications, 3 bad channels identified'
    )
    noise_test.save(db)
    print(f"   Recorded noise test")
    
    # 4. Update component status to qualified
    print("\n4. Updating component status to 'qualified'...")
    module.installation_status = 'qualified'
    module.current_location = 'Clean Room Storage'
    module.save(db)
    print(f"   Status updated: {module.installation_status}")
    
    # 5. Add a FEB
    print("\n5. Adding a FEB...")
    feb = Component(
        id='FEB-042',
        type='feb',
        serial_number='FEB-042-2024',
        manufacturer='SLAC',
        installation_status='spare',
        current_location='Electronics Lab',
        attributes={
            'slot_number': 5,
            'firmware_version': 'v2.3.1',
            'channels': 512
        }
    )
    feb.save(db)
    print(f"   Added FEB: {feb.id}")
    
    # 6. Install the module
    print("\n6. Installing module at Layer1_top_axial...")
    install_component(
        component_id='HPK-SN123456',
        position='Layer1_top_axial',
        run_period='2025_spring_run',
        installed_by='John Doe',
        notes='Installed for spring physics run',
        db=db
    )
    print(f"   Module installed")
    
    # 7. Query installed modules
    print("\n7. Querying installed modules...")
    installed = Component.list_all(
        component_type='module',
        status='installed',
        db=db
    )
    print(f"   Found {len(installed)} installed modules:")
    for comp in installed:
        print(f"      {comp.id} at {comp.installed_position}")
    
    # 8. Get test history
    print("\n8. Retrieving test history for HPK-SN123456...")
    tests = TestResult.get_for_component('HPK-SN123456', db)
    print(f"   Found {len(tests)} tests:")
    for test in tests:
        result = 'PASS' if test['pass_fail'] else 'FAIL' if test['pass_fail'] is not None else 'N/A'
        print(f"      {test['test_type']}: {result} ({test['test_date'][:19]})")
    
    # 9. Show summary
    print("\n9. Database Summary:")
    with db.get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) as count FROM components").fetchone()
        print(f"   Total components: {total['count']}")
        
        by_type = conn.execute("""
            SELECT type, COUNT(*) as count 
            FROM components 
            GROUP BY type
        """).fetchall()
        for row in by_type:
            print(f"      {row['type']}: {row['count']}")
    
    print("\n" + "="*60)
    print("Example completed successfully!")
    print("Database location:", db.db_path)
    print("="*60)


if __name__ == '__main__':
    main()

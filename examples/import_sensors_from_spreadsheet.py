#!/usr/bin/env python3
"""
Import sensor data from HPS-2022-EC-before-after-cleaving spreadsheet

This script creates sensor components in the database with all measurement
data stored as attributes.

Usage:
    python examples/import_sensors_from_spreadsheet.py [--dry-run]
"""
import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from hps_svt_tracker.database import get_default_db
from hps_svt_tracker.models import Component


# Raw CSV data from the spreadsheet
CSV_DATA = """Wafer,Sensor,Center Deviation [um],L.C. @ 100V on wafer (A/cm2),Pinholes in sector A,Pinholes in sector B,State,EDGE A distance to the cleaving path (µm),Centre distance to the cleaving path (µm),EDGE B distance to the cleaving path (µm),L.C. @ 100V cleaved (A/cm2),L.C. @ 100V SCIPP IV (A/cm2),Ratio,IV Tested at SCIPP,Comments,Edge imaged
W1,S2,163,8.85e-06,,,cleaved,0,163,227,9.01e-06,,,Yes,High current,
W1,S3,57,2.55e-07,,"135,187,189,195,197,188,190,196",cleaved,0,57,155,2.80e-07,3.53E-07,1.260734275,Yes,,Yes
W1,S4,59,2.50e-07,226,,cleaved,0,59,151,2.84e-07,3.34E-07,1.174565115,Yes,,
W1,S5,138,3.51e-07,,,cleaved,0,128,229,2.91e-07,3.33E-07,1.14300277,Yes,,
W1,S6,170,2.73e-07,,,cleaved,0,170,237,2.70e-07,3.64E-07,1.347961581,Yes,,
W2,S1,80,2.60e-07,102,,cleaved,0,80,186,2.76e-07,3.06E-07,1.107343716,Yes,,
W2,S2,163,2.12e-07,,,cleaved,0,163,235,2.35e-07,2.66E-07,1.131652906,Yes,,
W2,S4,171,2.24e-07,226,,cleaved,0,171,226,2.72e-07,3.28E-07,1.205731453,Yes,,
W2,S5,52,2.47e-07,145.148,,cleaved,0,52,149,3.49e-07,3.78E-07,1.082126973,Yes,"Bottom left edge chip, isolated to passive area",
W2,S6,169,2.33e-07,"49,51,50,52","99,103,102,120",cleaved,0,169,236,3.11e-07,4.68E-07,1.504697173,Yes,,
W3,S1,175,2.47e-07,"117,119,121,123,102,116,118,120,122",,cleaved,0,175,200,2.27e-07,2.76E-07,1.214913867,Yes,Large scratch,
W3,S2,175,2.08e-07,,,cleaved,0,175,220,1.29e-07,1.56E-07,1.212397316,Yes,,
W3,S3,30,2.42e-07,,,cleaved,0,30,150,2.17e-07,2.69E-07,1.23982908,Yes,,
W3,S4,60,2.25e-07,,,cleaved,0,60,140,1.98e-07,2.86E-07,1.445066335,Yes,,
W3,S5,60,2.94e-07,"137,143,145,138,140,146",,cleaved,0,60,190,3.13e-07,2.99E-07,0.9563921606,Yes,Higher current for bias > 100 V,
W3,S6,180,2.31e-07,,,cleaved,0,180,240,2.15e-07,2.62E-07,1.217216244,Yes,,
W4,S1,170,2.38e-07,102,,cleaved,0,170,220,2.25e-07,2.59E-07,1.149809287,Yes,Lots of surface level scratches,
W4,S2,175,1.97e-07,,,cleaved,0,175,210,1.73e-07,1.71E-07,0.9906252696,Yes,,
W4,S3,60,2.37e-07,,,cleaved,0,60,180,2.20e-07,2.98E-07,1.355164518,Yes,,
W4,S4,150,2.26e-07,226,,cleaved,0,150,0,4.00e-07,2.81E-07,0.7034981343,Yes,,
W4,S6,175,2.29e-07,,189,cleaved,0,175,230,2.13e-07,2.61E-07,1.224414897,Yes,,
W5,S1,90,2.42e-07,102,,cleaved,0,90,190,2.26e-07,3.69E-07,1.632619535,Yes,,
W5,S2,175,2.01e-07,,,cleaved,0,175,240,1.33e-07,2.60E-07,1.953807092,Yes,,
W5,S3,60,2.42e-07,,,cleaved,0,60,150,2.31e-07,4.05E-07,1.751542612,Yes,,
W5,S4,20,2.30e-07,226,,cleaved,0,20,110,2.13e-07,7.24E-07,3.398955925,Yes,,
W5,S6,180,2.38e-07,,,cleaved,0,180,240,2.24e-07,5.32E-07,2.376257663,Yes,,
W6,S1,175,4.08e-06,102,,cleaved,0,175,230,>1e-05,3.30E-06,,Yes,,
W6,S2,175,2.18e-07,,,cleaved,0,175,210,1.59e-07,3.08E-07,1.937893082,Yes,,
W6,S3,175,2.42e-07,,,cleaved,220,175,0,2.22e-07,3.72E-07,1.676784994,Yes,,
W6,S4,25,2.34e-07,,,cleaved,0,25,120,4.49e-07,3.77E-07,0.8393112389,Yes,,Yes
W6,S5,100,2.46e-07,,,cleaved,0,100,200,2.49e-07,3.73E-07,1.499625367,Yes,,
W6,S6,200,2.40e-07,,,cleaved,0,200,240,2.15e-07,3.67E-07,1.708365151,Yes,,
W7,S3,100,2.44e-07,,,cleaved,0,100,220,2.34e-07,3.27E-07,1.399325488,Yes,,
W7,S4,110,2.40e-07,,,cleaved,0,110,190,2.25e-07,3.55E-07,1.575878939,Yes,"Initial IV showed weird step at 40V, restarted and went away.",
W7,S5,180,2.65e-07,,,cleaved,0,180,230,2.42e-07,3.09E-07,1.278285741,Yes,,
W7,S6,135,2.49e-07,,,cleaved,0,135,220,2.41e-07,3.17E-07,1.31328575,Yes,Pin gave issues and left some marks,
W8,S1,175,5.36e-06,102,,cleaved,0,175,240,5.36e-06,3.72E-06,0.6940646581,Yes,,
W8,S2,140,2.40e-07,233,,cleaved,0,140,240,1.70e-07,2.99E-07,1.75928446,Yes,,
W8,S3,45,2.69e-07,,,cleaved,0,45,150,2.97e-07,5.49E-07,1.849471079,Yes,,Yes
W8,S4,45,2.75e-07,226,,cleaved,0,45,150,2.70e-07,4.63E-07,1.713605583,Yes,,Yes
W8,S5,70,2.81e-07,,,cleaved,0,70,150,2.66e-07,7.07E-07,2.658483896,Yes,,Yes
W8,S6,180,2.79e-07,,,cleaved,0,180,220,2.76e-07,5.11E-07,1.849901309,Yes,,
W9,S1,160,2.71e-07,151.102,,cleaved,0,160,240,2.62e-07,3.99E-07,1.521391136,Yes,,
W9,S2,190,2.45e-07,,,cleaved,0,190,240,1.92e-07,3.14E-07,1.637845927,Yes,,
W9,S3,105,2.63e-07,,78,cleaved,70,105,150,2.58e-07,4.20E-07,1.629346003,Yes,,
W9,S4,30,2.52e-07,226,,cleaved,0,30,110,2.37e-07,3.70E-07,1.560457208,Yes,,Yes
W9,S5,35,2.76e-07,,,cleaved,0,35,145,2.55e-07,3.88E-07,1.520976002,Yes,,Yes
W9,S6,137,2.61e-07,,,cleaved,0,137,240,2.48e-07,4.06E-07,1.638420799,Yes,,
W10,S1,160,2.71e-07,247.102,,cleaved,0,160,240,3.94e-07,,0,Yes,,
W10,S2,135,1.76e-07,,,cleaved,0,135,240,1.09e-07,,0,Yes,,
W10,S3,25,2.38e-07,,,cleaved,0,25,140,2.49e-07,3.74E-07,1.500134868,Yes,,Yes
W10,S4,50,2.30e-07,,,cleaved,0,50,110,2.26e-07,4.14E-07,1.832295932,Yes,,Yes
W10,S5,105,2.33e-07,,,cleaved,0,105,190,2.22e-07,,0,,,
W10,S6,180,2.31e-07,,,cleaved,0,180,220,2.23e-07,,0,,,
W11,S1,85,2.43e-07,102,,cleaved,0,85,190,3.67e-07,,0,,,
W11,S2,175,1.92e-07,,,cleaved,0,175,230,9.64e-08,,0,,,
W11,S3,66,6.47e-6,,,cleaved,0,66,150,6.37e-06,,0,,,
W11,S4,137,2.31e-07,,,cleaved,0,137,190,2.14e-07,,0,,,
W11,S5,150,2.44e-07,,,cleaved,0,150,220,2.36e-07,,0,,,
W11,S6,175,2.27e-07,,,cleaved,0,175,240,2.20e-07,,0,,,
W14,S1,180,2.41e-07,102,,cleaved,0,180,240,2.22e-07,,0,,Very scratched near bias pad,
W14,S2,170,2.15e-07,,,cleaved,0,170,240,1.67e-07,,0,,,
W14,S5,,2.27e-07,,,cleaved,0,76,155,2.11e-07,,0,,,"""


def parse_value(value: str):
    """Parse a CSV value, converting to appropriate type"""
    if not value or value.strip() == '':
        return None

    value = value.strip()

    # Handle special cases
    if value.startswith('>'):
        return value  # Keep as string like ">1e-05"
    if value == '#VALUE!':
        return None

    # Try to convert to float
    try:
        return float(value)
    except ValueError:
        pass

    # Return as string
    return value


def parse_csv():
    """Parse the CSV data and return list of sensor records"""
    lines = CSV_DATA.strip().split('\n')
    headers = [h.strip() for h in lines[0].split(',')]

    sensors = []
    current_wafer = None

    for line in lines[1:]:
        # Handle CSV with quoted fields containing commas
        values = []
        in_quotes = False
        current_value = ''

        for char in line:
            if char == '"':
                in_quotes = not in_quotes
            elif char == ',' and not in_quotes:
                values.append(current_value)
                current_value = ''
            else:
                current_value += char
        values.append(current_value)  # Don't forget the last value

        # Build record
        record = {}
        for i, header in enumerate(headers):
            if i < len(values):
                record[header] = parse_value(values[i])
            else:
                record[header] = None

        # Handle wafer continuation (empty wafer means use previous)
        if record.get('Wafer'):
            current_wafer = record['Wafer']
        else:
            record['Wafer'] = current_wafer

        # Clean up sensor name (remove asterisks)
        if record.get('Sensor'):
            record['Sensor'] = record['Sensor'].replace('*', '')

        sensors.append(record)

    return sensors


def create_sensor_id(record: dict) -> str:
    """Create sensor ID in format Wafer-Sensor-2025"""
    wafer = record['Wafer']
    sensor = record['Sensor']
    return f"{wafer}-{sensor}-2025"


def import_sensors(dry_run: bool = False):
    """Import all sensors into the database"""
    db = get_default_db()
    sensors = parse_csv()

    print(f"Found {len(sensors)} sensors to import")
    print("-" * 60)

    created = 0
    updated = 0
    errors = 0

    for record in sensors:
        sensor_id = create_sensor_id(record)

        # Build attributes dict from all columns except Wafer and Sensor
        attributes = {}
        for key, value in record.items():
            if key not in ('Wafer', 'Sensor') and value is not None:
                attributes[key] = value

        # Add original wafer/sensor for reference
        attributes['Original Wafer'] = record['Wafer']
        attributes['Original Sensor'] = record['Sensor']

        try:
            # Check if sensor already exists
            existing = Component.get(sensor_id, db)

            if existing:
                if dry_run:
                    print(f"[DRY-RUN] Would update: {sensor_id}")
                else:
                    existing.update_attributes(attributes)
                    existing.save(db)
                    print(f"Updated: {sensor_id}")
                updated += 1
            else:
                if dry_run:
                    print(f"[DRY-RUN] Would create: {sensor_id}")
                    print(f"          Attributes: {len(attributes)} fields")
                else:
                    sensor = Component(
                        id=sensor_id,
                        type='sensor',
                        installation_status='incoming',
                        manufacturer='CNM',
                        attributes=attributes
                    )
                    sensor.save(db)
                    print(f"Created: {sensor_id}")
                created += 1

        except Exception as e:
            print(f"Error processing {sensor_id}: {e}")
            errors += 1

    print("-" * 60)
    print(f"Summary: {created} created, {updated} updated, {errors} errors")

    if dry_run:
        print("\n[DRY-RUN] No changes were made to the database.")

    return created, updated, errors


def main():
    parser = argparse.ArgumentParser(
        description='Import sensor data from HPS-2022 spreadsheet'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Show what would be imported without making changes'
    )

    args = parser.parse_args()

    print("HPS Sensor Import Script")
    print("=" * 60)
    print(f"Source: HPS-2022-EC-before-after-cleaving.xlsx")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print("=" * 60)
    print()

    import_sensors(dry_run=args.dry_run)


if __name__ == '__main__':
    main()

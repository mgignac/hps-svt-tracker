#!/usr/bin/env python3
"""
Register 10 Flange Boards (Flange-C03-01 through Flange-C03-10)

These flange boards are located at SLAC and are currently being tested.
"""

from hps_svt_tracker import Component, get_default_db


def main():
    db = get_default_db()

    print("=" * 60)
    print("Registering 10 Flange Boards (Flange-C03-01 through Flange-C03-10)")
    print("Location: SLAC")
    print("Status: testing")
    print("=" * 60)

    for i in range(1, 11):
        flange_id = f"Flange-C03-{i:02d}"

        flange = Component(
            id=flange_id,
            type='flange_board',
            serial_number=flange_id,
            installation_status='testing',
            current_location='SLAC',
        )
        flange.save(db)
        print(f"  Registered: {flange_id}")

    print("=" * 60)
    print("Done! Registered 10 Flange Boards.")
    print("=" * 60)


if __name__ == '__main__':
    main()

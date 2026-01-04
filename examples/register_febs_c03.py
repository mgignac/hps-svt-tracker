#!/usr/bin/env python3
"""
Register 20 FEBs (FEB-C03-01 through FEB-C03-20)

These FEBs are located at SLAC and are currently being tested.
"""

from hps_svt_tracker import Component, get_default_db


def main():
    db = get_default_db()

    print("=" * 60)
    print("Registering 20 FEBs (FEB-C03-01 through FEB-C03-20)")
    print("Location: SLAC")
    print("Status: testing")
    print("=" * 60)

    for i in range(1, 21):
        feb_id = f"FEB-C03-{i:02d}"

        feb = Component(
            id=feb_id,
            type='feb',
            serial_number=feb_id,
            installation_status='testing',
            current_location='SLAC',
        )
        feb.save(db)
        print(f"  Registered: {feb_id}")

    print("=" * 60)
    print("Done! Registered 20 FEBs.")
    print("=" * 60)


if __name__ == '__main__':
    main()

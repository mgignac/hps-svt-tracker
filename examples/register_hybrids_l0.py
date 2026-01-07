#!/usr/bin/env python3
"""
Register 12 Layer 0 Hybrids (Hybrid-L0-01 through Hybrid-L0-12)

These hybrids are located at SLAC.
"""

from hps_svt_tracker import Component, get_default_db


def main():
    db = get_default_db()

    print("=" * 60)
    print("Registering 12 Hybrids (Hybrid-L0-01 through Hybrid-L0-12)")
    print("Location: SLAC")
    print("Status: incoming")
    print("=" * 60)

    for i in range(1, 13):
        hybrid_id = f"Hybrid-L0-{i:02d}"

        hybrid = Component(
            id=hybrid_id,
            type='hybrid',
            serial_number=hybrid_id,
            installation_status='incoming',
            current_location='SLAC',
        )
        hybrid.save(db)
        print(f"  Registered: {hybrid_id}")

    print("=" * 60)
    print("Done! Registered 12 hybrids.")
    print("=" * 60)


if __name__ == '__main__':
    main()

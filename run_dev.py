#!/usr/bin/env python3
"""
Development server launcher for HPS SVT Tracker web interface

Usage:
    python run_dev.py
"""
import sys
import os

# Add current directory to path to allow importing web module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import create_app
from web.config import DevelopmentConfig


if __name__ == '__main__':
    print("=" * 60)
    print("HPS SVT Tracker - Development Server")
    print("=" * 60)
    print()
    print("Starting Flask development server...")
    print("Access the web interface at: http://localhost:5000")
    print()
    print("Press CTRL+C to stop the server")
    print("=" * 60)
    print()

    app = create_app(DevelopmentConfig)
    app.run(host='0.0.0.0', port=5000, debug=True)

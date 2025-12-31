"""
HPS SVT Component Tracker - Setup Script
"""
from setuptools import setup, find_packages

setup(
    name="hps-svt-tracker",
    version="0.1.0",
    description="Component tracking and test management system for HPS SVT detector",
    author="HPS Collaboration",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "tabulate>=0.9",
        "python-dateutil>=2.8",
    ],
    entry_points={
        "console_scripts": [
            "svt=hps_svt_tracker.cli:cli",
        ],
    },
    python_requires=">=3.8",
)

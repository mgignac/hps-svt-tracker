"""
Plotting functions for HPS SVT Component Tracker

Generates summary plots for test results across components.
"""
import io
import json
from typing import Optional, List, Dict, Any, Tuple

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for server
import matplotlib.pyplot as plt

from .database import Database, get_default_db
from .models import Component, TestResult


def generate_edge_imaging_summary(db: Optional[Database] = None) -> Tuple[bytes, List[Dict[str, Any]]]:
    """
    Generate a summary plot of edge imaging test results across all sensors.

    Returns:
        Tuple of (PNG image bytes, list of sensor data included in plot)

    Each sensor's latest edge imaging test is plotted with:
    - Data point at edge_gap_mean
    - Error bars from edge_gap_min to edge_gap_max
    """
    if db is None:
        db = get_default_db()

    # Get all sensors
    sensors = Component.list_all(component_type='sensor', db=db)

    # Collect data for each sensor
    plot_data = []

    for sensor in sensors:
        # Get all test results for this sensor
        tests = TestResult.get_for_component(sensor.id, db=db)

        # Filter to edge_imaging tests only
        edge_tests = [t for t in tests if t['test_type'] == 'edge_imaging']

        if not edge_tests:
            continue

        # Get the most recent edge imaging test
        latest_test = edge_tests[0]  # Already sorted by test_date DESC

        # Parse measurements
        measurements = {}
        if latest_test['measurements_json']:
            try:
                measurements = json.loads(latest_test['measurements_json'])
            except json.JSONDecodeError:
                continue

        # Extract edge gap values
        edge_gap_mean = measurements.get('edge_gap_mean')
        edge_gap_min = measurements.get('edge_gap_min')
        edge_gap_max = measurements.get('edge_gap_max')

        # Skip if no mean value
        if edge_gap_mean is None:
            continue

        plot_data.append({
            'sensor_id': sensor.id,
            'mean': edge_gap_mean,
            'min': edge_gap_min if edge_gap_min is not None else edge_gap_mean,
            'max': edge_gap_max if edge_gap_max is not None else edge_gap_mean,
            'test_date': latest_test['test_date'],
            'pass_fail': latest_test['pass_fail']
        })

    # Sort by sensor ID for consistent ordering
    plot_data.sort(key=lambda x: x['sensor_id'])

    # Create the plot
    fig, ax = plt.subplots(figsize=(max(10, len(plot_data) * 0.8), 6))

    if not plot_data:
        ax.text(0.5, 0.5, 'No edge imaging test data available',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=14, color='gray')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    else:
        # Prepare data for plotting
        x_positions = range(len(plot_data))
        means = [d['mean'] for d in plot_data]
        labels = [d['sensor_id'] for d in plot_data]

        # Calculate asymmetric error bars
        yerr_lower = [d['mean'] - d['min'] for d in plot_data]
        yerr_upper = [d['max'] - d['mean'] for d in plot_data]

        # Plot with error bars
        ax.errorbar(x_positions, means, yerr=[yerr_lower, yerr_upper],
                   fmt='o', markersize=8, capsize=5, capthick=2,
                   color='#1f77b4', ecolor='#1f77b4', elinewidth=2)

        # Customize axes
        ax.set_xticks(x_positions)
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_xlabel('Sensor ID', fontsize=12)
        ax.set_ylabel('Edge Gap (um)', fontsize=12)
        ax.set_title('Edge Imaging Results by Sensor', fontsize=14, fontweight='bold')

        # Add grid for readability
        ax.grid(True, axis='y', linestyle='--', alpha=0.7)
        ax.set_axisbelow(True)

        # Add some padding
        ax.margins(x=0.05)

    plt.tight_layout()

    # Save to bytes
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf.getvalue(), plot_data


def generate_cleaving_distance_plot(db: Optional[Database] = None) -> Tuple[bytes, List[Dict[str, Any]]]:
    """
    Generate a scatter plot of cleaving path distances across all sensors.

    Plots three series:
    - Centre distance to the cleaving path
    - EDGE A distance to the cleaving path
    - EDGE B distance to the cleaving path

    Returns:
        Tuple of (PNG image bytes, list of sensor data included in plot)
    """
    if db is None:
        db = get_default_db()

    # Attribute keys
    CENTRE_KEY = 'Centre distance to the cleaving path (µm)'
    EDGE_A_KEY = 'EDGE A distance to the cleaving path (µm)'
    EDGE_B_KEY = 'EDGE B distance to the cleaving path (µm)'

    # Get all sensors
    sensors = Component.list_all(component_type='sensor', db=db)

    # Collect data for each sensor
    plot_data = []

    for sensor in sensors:
        centre = sensor.get_attribute(CENTRE_KEY)
        edge_a = sensor.get_attribute(EDGE_A_KEY)
        edge_b = sensor.get_attribute(EDGE_B_KEY)

        # Skip if none of the values are present
        if centre is None and edge_a is None and edge_b is None:
            continue

        # Convert to float where possible
        try:
            centre = float(centre) if centre is not None else None
        except (ValueError, TypeError):
            centre = None
        try:
            edge_a = float(edge_a) if edge_a is not None else None
        except (ValueError, TypeError):
            edge_a = None
        try:
            edge_b = float(edge_b) if edge_b is not None else None
        except (ValueError, TypeError):
            edge_b = None

        if centre is None and edge_a is None and edge_b is None:
            continue

        plot_data.append({
            'sensor_id': sensor.id,
            'centre': centre,
            'edge_a': edge_a,
            'edge_b': edge_b,
        })

    # Sort by sensor ID for consistent ordering
    plot_data.sort(key=lambda x: x['sensor_id'])

    # Create the plot
    fig, ax = plt.subplots(figsize=(max(10, len(plot_data) * 0.8), 6))

    if not plot_data:
        ax.text(0.5, 0.5, 'No cleaving distance data available',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=14, color='gray')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    else:
        x_positions = list(range(len(plot_data)))
        labels = [d['sensor_id'] for d in plot_data]

        # Plot each series with slight x offset for visibility
        offset = 0.15

        # Centre
        centre_vals = [(i, d['centre']) for i, d in enumerate(plot_data) if d['centre'] is not None]
        if centre_vals:
            ax.scatter([x - offset for x, _ in centre_vals], [v for _, v in centre_vals],
                      s=60, marker='o', color='#1f77b4', label='Centre', zorder=3)

        # Edge A
        edge_a_vals = [(i, d['edge_a']) for i, d in enumerate(plot_data) if d['edge_a'] is not None]
        if edge_a_vals:
            ax.scatter([x for x, _ in edge_a_vals], [v for _, v in edge_a_vals],
                      s=60, marker='s', color='#2ca02c', label='Edge A', zorder=3)

        # Edge B
        edge_b_vals = [(i, d['edge_b']) for i, d in enumerate(plot_data) if d['edge_b'] is not None]
        if edge_b_vals:
            ax.scatter([x + offset for x, _ in edge_b_vals], [v for _, v in edge_b_vals],
                      s=60, marker='^', color='#d62728', label='Edge B', zorder=3)

        ax.set_xticks(x_positions)
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_xlabel('Sensor ID', fontsize=12)
        ax.set_ylabel('Distance to Cleaving Path (µm)', fontsize=12)
        ax.set_title('Cleaving Path Distances by Sensor', fontsize=14, fontweight='bold')

        ax.legend(loc='best')
        ax.grid(True, axis='y', linestyle='--', alpha=0.7)
        ax.set_axisbelow(True)
        ax.margins(x=0.05)

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf.getvalue(), plot_data


def generate_leakage_current_plot(db: Optional[Database] = None) -> Tuple[bytes, List[Dict[str, Any]]]:
    """
    Generate a scatter plot of leakage current measurements across all sensors.

    Plots two series:
    - L.C. @ 100V on wafer
    - L.C. @ 100V cleaved

    Returns:
        Tuple of (PNG image bytes, list of sensor data included in plot)
    """
    if db is None:
        db = get_default_db()

    # Attribute keys
    WAFER_KEY = 'L.C. @ 100V on wafer (A/cm2)'
    CLEAVED_KEY = 'L.C. @ 100V cleaved (A/cm2)'

    # Get all sensors
    sensors = Component.list_all(component_type='sensor', db=db)

    # Collect data for each sensor
    plot_data = []

    for sensor in sensors:
        wafer = sensor.get_attribute(WAFER_KEY)
        cleaved = sensor.get_attribute(CLEAVED_KEY)

        # Skip if neither value is present
        if wafer is None and cleaved is None:
            continue

        # Convert to float where possible
        try:
            wafer = float(wafer) if wafer is not None else None
        except (ValueError, TypeError):
            wafer = None
        try:
            cleaved = float(cleaved) if cleaved is not None else None
        except (ValueError, TypeError):
            cleaved = None

        if wafer is None and cleaved is None:
            continue

        plot_data.append({
            'sensor_id': sensor.id,
            'wafer': wafer,
            'cleaved': cleaved,
        })

    # Sort by sensor ID for consistent ordering
    plot_data.sort(key=lambda x: x['sensor_id'])

    # Create the plot
    fig, ax = plt.subplots(figsize=(max(10, len(plot_data) * 0.8), 6))

    if not plot_data:
        ax.text(0.5, 0.5, 'No leakage current data available',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=14, color='gray')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    else:
        x_positions = list(range(len(plot_data)))
        labels = [d['sensor_id'] for d in plot_data]

        # Plot each series with slight x offset for visibility
        offset = 0.1

        # Wafer
        wafer_vals = [(i, d['wafer']) for i, d in enumerate(plot_data) if d['wafer'] is not None]
        if wafer_vals:
            ax.scatter([x - offset for x, _ in wafer_vals], [v for _, v in wafer_vals],
                      s=60, marker='o', color='#1f77b4', label='On Wafer', zorder=3)

        # Cleaved
        cleaved_vals = [(i, d['cleaved']) for i, d in enumerate(plot_data) if d['cleaved'] is not None]
        if cleaved_vals:
            ax.scatter([x + offset for x, _ in cleaved_vals], [v for _, v in cleaved_vals],
                      s=60, marker='s', color='#ff7f0e', label='Cleaved', zorder=3)

        ax.set_xticks(x_positions)
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_xlabel('Sensor ID', fontsize=12)
        ax.set_ylabel('Leakage Current @ 100V (A/cm²)', fontsize=12)
        ax.set_title('Leakage Current by Sensor', fontsize=14, fontweight='bold')

        ax.legend(loc='best')
        ax.grid(True, axis='y', linestyle='--', alpha=0.7)
        ax.set_axisbelow(True)
        ax.margins(x=0.05)

        # Use scientific notation for y-axis if values are small
        ax.ticklabel_format(axis='y', style='scientific', scilimits=(-3, 3))

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf.getvalue(), plot_data


def generate_edge_imaging_minmax(db: Optional[Database] = None) -> Tuple[bytes, List[Dict[str, Any]]]:
    """
    Generate a scatter plot of edge imaging min/max values across all sensors.

    Returns:
        Tuple of (PNG image bytes, list of sensor data included in plot)

    Plots min and max values as separate scatter series for each sensor.
    """
    if db is None:
        db = get_default_db()

    # Get all sensors
    sensors = Component.list_all(component_type='sensor', db=db)

    # Collect data for each sensor
    plot_data = []

    for sensor in sensors:
        # Get all test results for this sensor
        tests = TestResult.get_for_component(sensor.id, db=db)

        # Filter to edge_imaging tests only
        edge_tests = [t for t in tests if t['test_type'] == 'edge_imaging']

        if not edge_tests:
            continue

        # Get the most recent edge imaging test
        latest_test = edge_tests[0]  # Already sorted by test_date DESC

        # Parse measurements
        measurements = {}
        if latest_test['measurements_json']:
            try:
                measurements = json.loads(latest_test['measurements_json'])
            except json.JSONDecodeError:
                continue

        # Extract edge gap values
        edge_gap_min = measurements.get('edge_gap_min')
        edge_gap_max = measurements.get('edge_gap_max')

        # Skip if no min/max values
        if edge_gap_min is None and edge_gap_max is None:
            continue

        plot_data.append({
            'sensor_id': sensor.id,
            'min': edge_gap_min,
            'max': edge_gap_max,
            'test_date': latest_test['test_date'],
        })

    # Sort by sensor ID for consistent ordering
    plot_data.sort(key=lambda x: x['sensor_id'])

    # Create the plot
    fig, ax = plt.subplots(figsize=(max(10, len(plot_data) * 0.8), 6))

    if not plot_data:
        ax.text(0.5, 0.5, 'No edge imaging test data available',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=14, color='gray')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    else:
        # Prepare data for plotting
        x_positions = range(len(plot_data))
        labels = [d['sensor_id'] for d in plot_data]
        mins = [d['min'] for d in plot_data]
        maxs = [d['max'] for d in plot_data]

        # Plot min and max as separate series
        ax.scatter(x_positions, mins, s=60, marker='v', color='#2ca02c', label='Min', zorder=3)
        ax.scatter(x_positions, maxs, s=60, marker='^', color='#d62728', label='Max', zorder=3)

        # Customize axes
        ax.set_xticks(x_positions)
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_xlabel('Sensor ID', fontsize=12)
        ax.set_ylabel('Edge Gap (um)', fontsize=12)
        ax.set_title('Edge Imaging Min/Max Values by Sensor', fontsize=14, fontweight='bold')

        # Add legend
        ax.legend(loc='best')

        # Add grid for readability
        ax.grid(True, axis='y', linestyle='--', alpha=0.7)
        ax.set_axisbelow(True)

        # Add some padding
        ax.margins(x=0.05)

    plt.tight_layout()

    # Save to bytes
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf.getvalue(), plot_data

"""
Plotting functions for HPS SVT Component Tracker

Generates summary plots for test results across components.
"""
import io
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for server
import matplotlib.pyplot as plt
import numpy as np

from .database import Database, get_default_db
from .models import Component, TestResult


# =============================================================================
# IV Curve Analysis Functions
# =============================================================================

def read_iv_data(file_path: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    Read IV (current-voltage) data from a file.

    Supports:
    - Excel files (.xlsx, .xls): First column = voltage, second column = current
    - CSV files (.csv): First column = voltage, second column = current
    - Text files (.txt, .dat, .tsv): Space/tab/comma separated

    Args:
        file_path: Path to the data file

    Returns:
        Tuple of (voltage_array, current_array) as numpy arrays

    Raises:
        ValueError: If file format is not supported or data cannot be parsed
    """
    ext = Path(file_path).suffix.lower()

    if ext in ('.xlsx', '.xls'):
        # Excel file
        try:
            import pandas as pd
            df = pd.read_excel(file_path, header=None)
            # Assume first row might be header if non-numeric
            try:
                float(df.iloc[0, 0])
                # First row is data
                voltage = df.iloc[:, 0].astype(float).values
                current = df.iloc[:, 1].astype(float).values
            except (ValueError, TypeError):
                # First row is header, skip it
                voltage = df.iloc[1:, 0].astype(float).values
                current = df.iloc[1:, 1].astype(float).values
        except ImportError:
            raise ValueError("pandas and openpyxl are required to read Excel files. "
                           "Install with: pip install pandas openpyxl")

    elif ext == '.csv':
        # CSV file
        try:
            data = np.genfromtxt(file_path, delimiter=',', skip_header=0)
            if np.isnan(data[0, 0]):
                # First row was header
                data = np.genfromtxt(file_path, delimiter=',', skip_header=1)
            voltage = data[:, 0]
            current = data[:, 1]
        except Exception as e:
            raise ValueError(f"Could not parse CSV file: {e}")

    elif ext in ('.txt', '.dat', '.tsv'):
        # Text file - try various delimiters
        for delimiter in ['\t', ' ', ',', ';']:
            try:
                data = np.genfromtxt(file_path, delimiter=delimiter, skip_header=0)
                if data.ndim == 2 and data.shape[1] >= 2:
                    if np.isnan(data[0, 0]):
                        data = np.genfromtxt(file_path, delimiter=delimiter, skip_header=1)
                    voltage = data[:, 0]
                    current = data[:, 1]
                    break
            except Exception:
                continue
        else:
            raise ValueError("Could not parse text file with any common delimiter")

    else:
        raise ValueError(f"Unsupported file format: {ext}")

    # Validate data
    if len(voltage) == 0 or len(current) == 0:
        raise ValueError("No data found in file")

    if len(voltage) != len(current):
        raise ValueError("Voltage and current arrays have different lengths")

    return voltage, current


def analyze_iv_data(voltage: np.ndarray, current: np.ndarray) -> Dict[str, Any]:
    """
    Analyze IV curve data and extract key measurements.

    Args:
        voltage: Array of voltage values (V)
        current: Array of current values (A)

    Returns:
        Dictionary containing:
        - voltage_max: Maximum voltage in the data
        - voltage_min: Minimum voltage in the data
        - current_at_max_voltage: Current at maximum voltage
        - current_max: Maximum current
        - current_min: Minimum current
        - current_mean: Mean current
        - num_points: Number of data points
        - voltage_values: List of all voltage values
        - current_values: List of all current values
    """
    # Sort by voltage for consistent analysis
    sort_idx = np.argsort(voltage)
    voltage = voltage[sort_idx]
    current = current[sort_idx]

    # Take absolute values of current (can be negative in some measurement setups)
    current_abs = np.abs(current)

    measurements = {
        'voltage_max': float(voltage.max()),
        'voltage_min': float(voltage.min()),
        'voltage_measured': float(voltage.max()),  # For compatibility with existing schema
        'current_at_max_voltage': float(current_abs[np.argmax(voltage)]),
        'current_measured': float(current_abs[np.argmax(voltage)]),  # For compatibility
        'current_max': float(current_abs.max()),
        'current_min': float(current_abs.min()),
        'current_mean': float(current_abs.mean()),
        'num_points': len(voltage),
        'voltage_values': voltage.tolist(),
        'current_values': current.tolist(),
    }

    return measurements


def generate_iv_curve_plot(voltage: np.ndarray, current: np.ndarray,
                           component_id: str = None,
                           title: str = None) -> bytes:
    """
    Generate an IV curve plot.

    Args:
        voltage: Array of voltage values (V)
        current: Array of current values (A)
        component_id: Optional component ID for the title
        title: Optional custom title

    Returns:
        PNG image as bytes
    """
    # Sort by voltage
    sort_idx = np.argsort(voltage)
    voltage = voltage[sort_idx]
    current = current[sort_idx]

    # Remove the first data point (often an outlier at 0V)
    if len(voltage) > 1:
        voltage = voltage[1:]
        current = current[1:]

    # Take absolute value of current and convert to µA
    current_ua = np.abs(current) * 1e6

    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot IV curve
    ax.plot(voltage, current_ua, 'b-', linewidth=1.5, marker='o', markersize=4)

    # Labels and title
    ax.set_xlabel('Bias Voltage (V)', fontsize=12)
    ax.set_ylabel('Leakage Current (µA)', fontsize=12)

    if title:
        ax.set_title(title, fontsize=14, fontweight='bold')
    elif component_id:
        ax.set_title(f'IV Curve - {component_id}', fontsize=14, fontweight='bold')
    else:
        ax.set_title('IV Curve', fontsize=14, fontweight='bold')

    # Grid
    ax.grid(True, linestyle='--', alpha=0.7)

    # Add annotation - prefer 100V if it exists, otherwise use max voltage
    annotation_idx = None
    annotation_voltage = None

    # Look for 100V in the data
    v100_indices = np.where(np.isclose(voltage, 100, atol=1))[0]
    if len(v100_indices) > 0:
        annotation_idx = v100_indices[0]
        annotation_voltage = voltage[annotation_idx]
    else:
        # Fall back to max voltage
        annotation_idx = np.argmax(voltage)
        annotation_voltage = voltage[annotation_idx]

    current_at_annotation = current_ua[annotation_idx]
    ax.annotate(f'I @ {annotation_voltage:.0f}V = {current_at_annotation:.2f} µA',
                xy=(annotation_voltage, current_at_annotation),
                xytext=(0.7, 0.9), textcoords='axes fraction',
                fontsize=10,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0.2'))

    plt.tight_layout()

    # Save to bytes
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf.getvalue()


def analyze_iv_file(file_path: str, component_id: str = None) -> Dict[str, Any]:
    """
    Read and analyze an IV data file, returning measurements and plot.

    Args:
        file_path: Path to the IV data file
        component_id: Optional component ID for plot title

    Returns:
        Dictionary containing:
        - measurements: Extracted measurements dict
        - plot_bytes: PNG plot as bytes
        - success: Boolean indicating success
        - error: Error message if failed
    """
    try:
        voltage, current = read_iv_data(file_path)
        measurements = analyze_iv_data(voltage, current)
        plot_bytes = generate_iv_curve_plot(voltage, current, component_id)

        return {
            'success': True,
            'measurements': measurements,
            'plot_bytes': plot_bytes,
            'error': None
        }
    except Exception as e:
        return {
            'success': False,
            'measurements': {},
            'plot_bytes': None,
            'error': str(e)
        }


# =============================================================================
# Summary Plot Functions
# =============================================================================


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


def generate_edge_imaging_lcr_plot(db: Optional[Database] = None) -> Tuple[bytes, List[Dict[str, Any]]]:
    """
    Generate a scatter plot of L, C, R edge gap values across all sensors.

    Plots three series:
    - L (Left) edge gap mean
    - C (Center) edge gap mean
    - R (Right) edge gap mean

    Only includes sensors that have all three measurements.

    Returns:
        Tuple of (PNG image bytes, list of sensor data included in plot)
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

        # Extract L, C, R values
        l_mean = measurements.get('edge_gap_l_mean')
        c_mean = measurements.get('edge_gap_c_mean')
        r_mean = measurements.get('edge_gap_r_mean')

        # Only include if at least one position measurement exists
        if l_mean is None and c_mean is None and r_mean is None:
            continue

        plot_data.append({
            'sensor_id': sensor.id,
            'l_mean': l_mean,
            'c_mean': c_mean,
            'r_mean': r_mean,
            'test_date': latest_test['test_date'],
        })

    # Sort by sensor ID for consistent ordering
    plot_data.sort(key=lambda x: x['sensor_id'])

    # Create the plot
    fig, ax = plt.subplots(figsize=(max(10, len(plot_data) * 0.8), 6))

    if not plot_data:
        ax.text(0.5, 0.5, 'No edge imaging L/C/R data available',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=14, color='gray')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    else:
        x_positions = list(range(len(plot_data)))
        labels = [d['sensor_id'] for d in plot_data]

        # Plot each series with slight x offset for visibility
        offset = 0.2

        # L (Left)
        l_vals = [(i, d['l_mean']) for i, d in enumerate(plot_data) if d['l_mean'] is not None]
        if l_vals:
            ax.scatter([x - offset for x, _ in l_vals], [v for _, v in l_vals],
                      s=80, marker='<', color='#2ca02c', label='L (Left)', zorder=3)

        # C (Center)
        c_vals = [(i, d['c_mean']) for i, d in enumerate(plot_data) if d['c_mean'] is not None]
        if c_vals:
            ax.scatter([x for x, _ in c_vals], [v for _, v in c_vals],
                      s=80, marker='o', color='#1f77b4', label='C (Center)', zorder=3)

        # R (Right)
        r_vals = [(i, d['r_mean']) for i, d in enumerate(plot_data) if d['r_mean'] is not None]
        if r_vals:
            ax.scatter([x + offset for x, _ in r_vals], [v for _, v in r_vals],
                      s=80, marker='>', color='#d62728', label='R (Right)', zorder=3)

        ax.set_xticks(x_positions)
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_xlabel('Sensor ID', fontsize=12)
        ax.set_ylabel('Edge Gap (µm)', fontsize=12)
        ax.set_title('Edge Gap by Position (L/C/R)', fontsize=14, fontweight='bold')

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


def generate_edge_slope_plot(db: Optional[Database] = None) -> Tuple[bytes, List[Dict[str, Any]]]:
    """
    Generate a scatter plot of edge slope values across all sensors.

    Plots the edge slope in µm/mm for each sensor that has L, C, R measurements.
    Color-coded by R² fit quality.

    Returns:
        Tuple of (PNG image bytes, list of sensor data included in plot)
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

        # Extract slope values
        slope = measurements.get('edge_slope_um_per_mm')
        r_squared = measurements.get('edge_fit_r_squared')
        angle_deg = measurements.get('edge_angle_deg')

        # Only include if slope exists
        if slope is None:
            continue

        plot_data.append({
            'sensor_id': sensor.id,
            'slope': slope,
            'r_squared': r_squared if r_squared is not None else 0,
            'angle_deg': angle_deg,
            'test_date': latest_test['test_date'],
        })

    # Sort by sensor ID for consistent ordering
    plot_data.sort(key=lambda x: x['sensor_id'])

    # Create the plot
    fig, ax = plt.subplots(figsize=(max(10, len(plot_data) * 0.8), 6))

    if not plot_data:
        ax.text(0.5, 0.5, 'No edge slope data available',
                ha='center', va='center', transform=ax.transAxes,
                fontsize=14, color='gray')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    else:
        x_positions = list(range(len(plot_data)))
        labels = [d['sensor_id'] for d in plot_data]
        slopes = [d['slope'] for d in plot_data]
        r_squared_vals = [d['r_squared'] for d in plot_data]

        # Color bars by R² value
        colors = []
        for r2 in r_squared_vals:
            if r2 >= 0.9:
                colors.append('#2ca02c')  # Green for good fit
            elif r2 >= 0.7:
                colors.append('#ff7f0e')  # Orange for moderate fit
            else:
                colors.append('#d62728')  # Red for poor fit

        ax.scatter(x_positions, slopes, c=colors, s=80, edgecolor='black', linewidth=0.5, zorder=3)

        # Add a horizontal line at y=0 for reference
        ax.axhline(y=0, color='gray', linestyle='-', linewidth=0.5)

        ax.set_xticks(x_positions)
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_xlabel('Sensor ID', fontsize=12)
        ax.set_ylabel('Edge Slope (µm/mm)', fontsize=12)
        ax.set_title('Edge Slope by Sensor', fontsize=14, fontweight='bold')

        # Add legend for R² colors
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#2ca02c', edgecolor='black', label='R² ≥ 0.9 (good fit)'),
            Patch(facecolor='#ff7f0e', edgecolor='black', label='R² ≥ 0.7 (moderate)'),
            Patch(facecolor='#d62728', edgecolor='black', label='R² < 0.7 (poor fit)'),
        ]
        ax.legend(handles=legend_elements, loc='best')

        ax.grid(True, axis='y', linestyle='--', alpha=0.7)
        ax.set_axisbelow(True)
        ax.margins(x=0.05)

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)

    return buf.getvalue(), plot_data


def generate_edge_correlation_plots(db: Optional[Database] = None) -> Tuple[bytes, List[Dict[str, Any]]]:
    """
    Generate correlation plots between edge imaging measurements (L, C, R) and CNM edge attributes.

    Correlations:
    - Left (L) edge gap vs CNM Edge A distance
    - Right (R) edge gap vs CNM Edge B distance
    - Center (C) edge gap vs CNM Centre distance

    Returns:
        Tuple of (PNG image bytes, list of sensor data included in plot)
    """
    if db is None:
        db = get_default_db()

    # CNM attribute keys
    CENTRE_KEY = 'Centre distance to the cleaving path (µm)'
    EDGE_A_KEY = 'EDGE A distance to the cleaving path (µm)'
    EDGE_B_KEY = 'EDGE B distance to the cleaving path (µm)'

    # Get all sensors
    sensors = Component.list_all(component_type='sensor', db=db)

    # Collect data for each sensor
    plot_data = []

    for sensor in sensors:
        # Get CNM edge attributes
        centre_cnm = sensor.get_attribute(CENTRE_KEY)
        edge_a_cnm = sensor.get_attribute(EDGE_A_KEY)
        edge_b_cnm = sensor.get_attribute(EDGE_B_KEY)

        # Convert to float where possible
        try:
            centre_cnm = float(centre_cnm) if centre_cnm is not None else None
        except (ValueError, TypeError):
            centre_cnm = None
        try:
            edge_a_cnm = float(edge_a_cnm) if edge_a_cnm is not None else None
        except (ValueError, TypeError):
            edge_a_cnm = None
        try:
            edge_b_cnm = float(edge_b_cnm) if edge_b_cnm is not None else None
        except (ValueError, TypeError):
            edge_b_cnm = None

        # Get edge imaging test results
        tests = TestResult.get_for_component(sensor.id, db=db)
        edge_tests = [t for t in tests if t['test_type'] == 'edge_imaging']

        if not edge_tests:
            continue

        # Get the most recent edge imaging test
        latest_test = edge_tests[0]

        # Parse measurements
        measurements = {}
        if latest_test['measurements_json']:
            try:
                measurements = json.loads(latest_test['measurements_json'])
            except json.JSONDecodeError:
                continue

        # Extract L, C, R edge gap values
        l_mean = measurements.get('edge_gap_l_mean')
        c_mean = measurements.get('edge_gap_c_mean')
        r_mean = measurements.get('edge_gap_r_mean')

        # Skip if no edge imaging measurements
        if l_mean is None and c_mean is None and r_mean is None:
            continue

        # Check if we have at least one valid pair for correlation
        has_l_pair = l_mean is not None and edge_a_cnm is not None
        has_c_pair = c_mean is not None and centre_cnm is not None
        has_r_pair = r_mean is not None and edge_b_cnm is not None

        if not (has_l_pair or has_c_pair or has_r_pair):
            continue

        plot_data.append({
            'sensor_id': sensor.id,
            'l_mean': l_mean,
            'c_mean': c_mean,
            'r_mean': r_mean,
            'edge_a_cnm': edge_a_cnm,
            'centre_cnm': centre_cnm,
            'edge_b_cnm': edge_b_cnm,
        })

    # Create a 1x3 subplot figure
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    def calc_correlation(x_vals, y_vals):
        """Calculate Pearson correlation coefficient."""
        if len(x_vals) < 2:
            return None
        n = len(x_vals)
        sum_x = sum(x_vals)
        sum_y = sum(y_vals)
        sum_xy = sum(x * y for x, y in zip(x_vals, y_vals))
        sum_x2 = sum(x * x for x in x_vals)
        sum_y2 = sum(y * y for y in y_vals)

        numerator = n * sum_xy - sum_x * sum_y
        denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5

        if denominator == 0:
            return None
        return numerator / denominator

    # Plot 1: Left (L) vs Edge A
    ax1 = axes[0]
    l_pairs = [(d['l_mean'], d['edge_a_cnm'], d['sensor_id'])
               for d in plot_data
               if d['l_mean'] is not None and d['edge_a_cnm'] is not None]

    if l_pairs:
        x_vals = [p[1] for p in l_pairs]  # Edge A (CNM)
        y_vals = [p[0] for p in l_pairs]  # L mean (edge imaging)
        labels = [p[2] for p in l_pairs]

        ax1.scatter(x_vals, y_vals, s=80, marker='<', color='#2ca02c', edgecolor='black', linewidth=0.5)

        # Add sensor labels
        for x, y, label in zip(x_vals, y_vals, labels):
            ax1.annotate(label, (x, y), fontsize=7, ha='left', va='bottom',
                        xytext=(3, 3), textcoords='offset points')

        # Calculate and display correlation and fit
        corr = calc_correlation(x_vals, y_vals)
        fit_text_parts = []
        if corr is not None:
            fit_text_parts.append(f'r = {corr:.3f}')

        # Add trend line
        if len(x_vals) >= 2 and max(x_vals) != min(x_vals):
            try:
                import numpy as np
                z = np.polyfit(x_vals, y_vals, 1)
                slope, intercept = z[0], z[1]
                p = np.poly1d(z)
                x_line = np.linspace(min(x_vals), max(x_vals), 100)
                ax1.plot(x_line, p(x_line), 'k--', alpha=0.5, linewidth=1)
                fit_text_parts.append(f'slope = {slope:.2f}')
                fit_text_parts.append(f'intercept = {intercept:.1f} µm')
            except Exception:
                pass  # Skip trend line if fitting fails

        if fit_text_parts:
            ax1.text(0.05, 0.95, '\n'.join(fit_text_parts), transform=ax1.transAxes,
                    fontsize=9, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    ax1.set_xlabel('CNM Edge A Distance (µm)', fontsize=10)
    ax1.set_ylabel('Edge Imaging L Mean (µm)', fontsize=10)
    ax1.set_title('Left Edge (L) vs CNM Edge A', fontsize=12, fontweight='bold')
    ax1.grid(True, linestyle='--', alpha=0.7)

    # Plot 2: Center (C) vs Centre
    ax2 = axes[1]
    c_pairs = [(d['c_mean'], d['centre_cnm'], d['sensor_id'])
               for d in plot_data
               if d['c_mean'] is not None and d['centre_cnm'] is not None]

    if c_pairs:
        x_vals = [p[1] for p in c_pairs]  # Centre (CNM)
        y_vals = [p[0] for p in c_pairs]  # C mean (edge imaging)
        labels = [p[2] for p in c_pairs]

        ax2.scatter(x_vals, y_vals, s=80, marker='o', color='#1f77b4', edgecolor='black', linewidth=0.5)

        # Add sensor labels
        for x, y, label in zip(x_vals, y_vals, labels):
            ax2.annotate(label, (x, y), fontsize=7, ha='left', va='bottom',
                        xytext=(3, 3), textcoords='offset points')

        # Calculate and display correlation and fit
        corr = calc_correlation(x_vals, y_vals)
        fit_text_parts = []
        if corr is not None:
            fit_text_parts.append(f'r = {corr:.3f}')

        # Add trend line
        if len(x_vals) >= 2 and max(x_vals) != min(x_vals):
            try:
                import numpy as np
                z = np.polyfit(x_vals, y_vals, 1)
                slope, intercept = z[0], z[1]
                p = np.poly1d(z)
                x_line = np.linspace(min(x_vals), max(x_vals), 100)
                ax2.plot(x_line, p(x_line), 'k--', alpha=0.5, linewidth=1)
                fit_text_parts.append(f'slope = {slope:.2f}')
                fit_text_parts.append(f'intercept = {intercept:.1f} µm')
            except Exception:
                pass  # Skip trend line if fitting fails

        if fit_text_parts:
            ax2.text(0.05, 0.95, '\n'.join(fit_text_parts), transform=ax2.transAxes,
                    fontsize=9, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    ax2.set_xlabel('CNM Centre Distance (µm)', fontsize=10)
    ax2.set_ylabel('Edge Imaging C Mean (µm)', fontsize=10)
    ax2.set_title('Center (C) vs CNM Centre', fontsize=12, fontweight='bold')
    ax2.grid(True, linestyle='--', alpha=0.7)

    # Plot 3: Right (R) vs Edge B
    ax3 = axes[2]
    r_pairs = [(d['r_mean'], d['edge_b_cnm'], d['sensor_id'])
               for d in plot_data
               if d['r_mean'] is not None and d['edge_b_cnm'] is not None]

    if r_pairs:
        x_vals = [p[1] for p in r_pairs]  # Edge B (CNM)
        y_vals = [p[0] for p in r_pairs]  # R mean (edge imaging)
        labels = [p[2] for p in r_pairs]

        ax3.scatter(x_vals, y_vals, s=80, marker='>', color='#d62728', edgecolor='black', linewidth=0.5)

        # Add sensor labels
        for x, y, label in zip(x_vals, y_vals, labels):
            ax3.annotate(label, (x, y), fontsize=7, ha='left', va='bottom',
                        xytext=(3, 3), textcoords='offset points')

        # Calculate and display correlation and fit
        corr = calc_correlation(x_vals, y_vals)
        fit_text_parts = []
        if corr is not None:
            fit_text_parts.append(f'r = {corr:.3f}')

        # Add trend line
        if len(x_vals) >= 2 and max(x_vals) != min(x_vals):
            try:
                import numpy as np
                z = np.polyfit(x_vals, y_vals, 1)
                slope, intercept = z[0], z[1]
                p = np.poly1d(z)
                x_line = np.linspace(min(x_vals), max(x_vals), 100)
                ax3.plot(x_line, p(x_line), 'k--', alpha=0.5, linewidth=1)
                fit_text_parts.append(f'slope = {slope:.2f}')
                fit_text_parts.append(f'intercept = {intercept:.1f} µm')
            except Exception:
                pass  # Skip trend line if fitting fails

        if fit_text_parts:
            ax3.text(0.05, 0.95, '\n'.join(fit_text_parts), transform=ax3.transAxes,
                    fontsize=9, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    ax3.set_xlabel('CNM Edge B Distance (µm)', fontsize=10)
    ax3.set_ylabel('Edge Imaging R Mean (µm)', fontsize=10)
    ax3.set_title('Right Edge (R) vs CNM Edge B', fontsize=12, fontweight='bold')
    ax3.grid(True, linestyle='--', alpha=0.7)

    # Handle empty plots
    for ax, pairs, name in [(ax1, l_pairs, 'Left/Edge A'),
                            (ax2, c_pairs, 'Center/Centre'),
                            (ax3, r_pairs, 'Right/Edge B')]:
        if not pairs:
            ax.text(0.5, 0.5, f'No {name} data available',
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=12, color='gray')

    plt.suptitle('Edge Distance Correlations: Edge Imaging vs CNM Measurements',
                 fontsize=14, fontweight='bold', y=1.02)
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

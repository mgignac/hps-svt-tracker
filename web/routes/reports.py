"""
Report routes for HPS SVT Tracker web interface

Provides summary plots and reports across components.
"""
from flask import Blueprint, render_template, g, Response

from hps_svt_tracker.plotting import (
    generate_edge_imaging_summary,
    generate_edge_imaging_minmax,
    generate_cleaving_distance_plot,
    generate_leakage_current_plot,
)


reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/edge-imaging-summary')
def edge_imaging_summary():
    """Display the edge imaging summary page with plot"""
    # Generate plot to get the list of sensors included
    _, sensor_data = generate_edge_imaging_summary(db=g.db)

    return render_template('reports/edge_imaging_summary.html',
                         sensor_data=sensor_data)


@reports_bp.route('/edge-imaging-summary.png')
def edge_imaging_summary_image():
    """Return the edge imaging summary plot as PNG image"""
    image_bytes, _ = generate_edge_imaging_summary(db=g.db)

    return Response(image_bytes, mimetype='image/png')


@reports_bp.route('/edge-imaging-minmax.png')
def edge_imaging_minmax_image():
    """Return the edge imaging min/max plot as PNG image"""
    image_bytes, _ = generate_edge_imaging_minmax(db=g.db)

    return Response(image_bytes, mimetype='image/png')


@reports_bp.route('/cleaving-distance.png')
def cleaving_distance_image():
    """Return the cleaving distance plot as PNG image"""
    image_bytes, _ = generate_cleaving_distance_plot(db=g.db)

    return Response(image_bytes, mimetype='image/png')


@reports_bp.route('/leakage-current.png')
def leakage_current_image():
    """Return the leakage current plot as PNG image"""
    image_bytes, _ = generate_leakage_current_plot(db=g.db)

    return Response(image_bytes, mimetype='image/png')

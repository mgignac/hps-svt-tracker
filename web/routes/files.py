"""
Secure file serving for test data files
Prevents directory traversal attacks and validates file paths
"""
from flask import Blueprint, send_from_directory, g, abort
import os


files_bp = Blueprint('files', __name__)


@files_bp.route('/<path:filepath>')
def serve_file(filepath):
    """
    Serve test data files securely

    Validates the file path to prevent directory traversal attacks
    and ensures files are only served from the data directory.
    """

    # Normalize the path to prevent directory traversal
    safe_path = os.path.normpath(filepath)

    # Check for directory traversal attempts
    if safe_path.startswith('..') or os.path.isabs(safe_path):
        abort(403, description="Access denied: invalid file path")

    # Build the full path
    full_path = os.path.join(g.db.data_dir, safe_path)

    # Ensure the final path is still within data_dir (prevent symlink attacks)
    real_full_path = os.path.realpath(full_path)
    real_data_dir = os.path.realpath(g.db.data_dir)

    if not real_full_path.startswith(real_data_dir):
        abort(403, description="Access denied: path outside data directory")

    # Check if file exists
    if not os.path.exists(real_full_path):
        abort(404, description=f"File not found: {safe_path}")

    # Check if it's actually a file (not a directory)
    if not os.path.isfile(real_full_path):
        abort(403, description="Access denied: not a file")

    # Serve the file
    directory = os.path.dirname(real_full_path)
    filename = os.path.basename(real_full_path)

    return send_from_directory(directory, filename)

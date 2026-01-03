"""
Upload routes for HPS SVT Tracker web interface
Handles file uploads including component images
"""
import os
import getpass
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, request, g, redirect, url_for, flash
from werkzeug.utils import secure_filename
from hps_svt_tracker.models import Component


upload_bp = Blueprint('upload', __name__)

# Allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'tif'}


def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_current_user():
    """Get current system username"""
    try:
        return getpass.getuser()
    except Exception:
        return 'unknown'


@upload_bp.route('/')
def index():
    """Main upload page with links to different upload actions"""
    return render_template('upload/index.html')


@upload_bp.route('/picture', methods=['GET', 'POST'])
def picture():
    """Upload a picture for a component"""
    if request.method == 'POST':
        # Get form data
        component_id = request.form.get('component_id', '').strip()
        description = request.form.get('description', '').strip()
        uploaded_by = request.form.get('uploaded_by', '').strip() or get_current_user()

        # Validate component exists
        if not component_id:
            flash('Component ID is required.', 'danger')
            return redirect(url_for('upload.picture'))

        component = Component.get(component_id, g.db)
        if not component:
            flash(f"Component '{component_id}' not found.", 'danger')
            return redirect(url_for('upload.picture'))

        # Check if files were uploaded
        if 'image' not in request.files:
            flash('No image files selected.', 'danger')
            return redirect(url_for('upload.picture'))

        files = request.files.getlist('image')
        if not files or all(f.filename == '' for f in files):
            flash('No image files selected.', 'danger')
            return redirect(url_for('upload.picture'))

        # Filter valid files
        valid_files = [f for f in files if f.filename != '' and allowed_file(f.filename)]
        invalid_count = len([f for f in files if f.filename != '' and not allowed_file(f.filename)])

        if not valid_files:
            flash(f'No valid image files. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}', 'danger')
            return redirect(url_for('upload.picture'))

        # Create storage directory: data_dir/images/component_id/
        images_dir = os.path.join(g.db.data_dir, 'images', component_id)
        os.makedirs(images_dir, exist_ok=True)

        # Process each file
        uploaded_count = 0
        base_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        with g.db.get_connection() as conn:
            for idx, file in enumerate(valid_files):
                # Generate unique filename with timestamp and index
                original_ext = Path(file.filename).suffix.lower()
                safe_filename = secure_filename(file.filename)
                base_name = Path(safe_filename).stem
                filename = f"{base_timestamp}_{idx:02d}_{base_name}{original_ext}"
                filepath = os.path.join(images_dir, filename)

                # Save the file
                file.save(filepath)

                # Store relative path for database
                rel_path = os.path.relpath(filepath, g.db.data_dir)

                # Save to database
                conn.execute("""
                    INSERT INTO component_images
                    (component_id, image_path, description, uploaded_by, upload_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (component_id, rel_path, description or None, uploaded_by,
                      datetime.now().isoformat()))
                uploaded_count += 1

            conn.commit()

        # Build success message
        msg = f'{uploaded_count} image{"s" if uploaded_count > 1 else ""} uploaded successfully for component {component_id}.'
        if invalid_count > 0:
            msg += f' ({invalid_count} file{"s" if invalid_count > 1 else ""} skipped due to invalid type.)'
        flash(msg, 'success')
        return redirect(url_for('components.component_detail', component_id=component_id))

    # GET request - show the upload form
    # Get list of component IDs for autocomplete/validation
    components = Component.list_all(db=g.db)
    component_ids = [c.id for c in components]

    # Check for pre-filled component_id from query parameter
    prefill_component_id = request.args.get('component_id', '')

    return render_template('upload/picture.html',
                         component_ids=component_ids,
                         prefill_component_id=prefill_component_id)

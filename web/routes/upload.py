"""
Upload routes for HPS SVT Tracker web interface
Handles file uploads including component images and test results
"""
import os
import getpass
import tempfile
import tarfile
import json
import shutil
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, request, g, redirect, url_for, flash
from werkzeug.utils import secure_filename
from hps_svt_tracker.models import Component, TestResult, add_maintenance_log, install_component


upload_bp = Blueprint('upload', __name__)

# Allowed image extensions
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'tif'}

# Allowed data file extensions
ALLOWED_DATA_EXTENSIONS = {'csv', 'txt', 'dat', 'tsv', 'hdf5', 'h5', 'root', 'json', 'xlsx', 'xls'}

# Legacy alias
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS


def allowed_file(filename, allowed_extensions=None):
    """Check if file has an allowed extension"""
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_EXTENSIONS
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


def allowed_image(filename):
    """Check if file is an allowed image type"""
    return allowed_file(filename, ALLOWED_IMAGE_EXTENSIONS)


def allowed_data(filename):
    """Check if file is an allowed data type"""
    return allowed_file(filename, ALLOWED_DATA_EXTENSIONS)


def save_temp_file(uploaded_file):
    """Save uploaded file to temp directory and return the path"""
    if not uploaded_file or uploaded_file.filename == '':
        return None

    # Create a temp file with the original extension
    ext = Path(uploaded_file.filename).suffix
    fd, temp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    uploaded_file.save(temp_path)
    return temp_path


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


@upload_bp.route('/iv-test', methods=['GET', 'POST'])
def iv_test():
    """Upload an IV (Current-Voltage) test result with automatic data analysis"""
    # Import IV analysis utilities
    try:
        from hps_svt_tracker.plotting import analyze_iv_file
        iv_analysis_available = True
    except ImportError:
        iv_analysis_available = False

    if request.method == 'POST':
        # Get form data
        component_id = request.form.get('component_id', '').strip()
        tested_by = request.form.get('tested_by', '').strip() or get_current_user()
        test_setup = request.form.get('test_setup', '').strip()
        test_conditions = request.form.get('test_conditions', '').strip()
        notes = request.form.get('notes', '').strip()
        analyze_data = request.form.get('analyze_data') == 'on'

        # Pass/fail
        pass_fail_value = request.form.get('pass_fail', '')
        pass_fail = None
        if pass_fail_value == 'pass':
            pass_fail = True
        elif pass_fail_value == 'fail':
            pass_fail = False

        # Validate component exists
        if not component_id:
            flash('Component ID is required.', 'danger')
            return redirect(url_for('upload.iv_test'))

        component = Component.get(component_id, g.db)
        if not component:
            flash(f"Component '{component_id}' not found.", 'danger')
            return redirect(url_for('upload.iv_test'))

        # Measurements will be populated by analysis
        measurements = {}

        # Process file uploads
        files = {}
        temp_files = []  # Track temp files for cleanup
        generated_plot_path = None  # Track auto-generated plot

        try:
            # Raw data files
            raw_data_files = request.files.getlist('raw_data')
            analyzable_extensions = {'.xlsx', '.xls', '.csv', '.txt', '.dat', '.tsv'}
            analyzed_file = None

            if raw_data_files:
                raw_data_paths = []
                for f in raw_data_files:
                    if f.filename != '':
                        if not allowed_data(f.filename):
                            flash(f"Invalid data file type: {f.filename}", 'warning')
                            continue
                        temp_path = save_temp_file(f)
                        if temp_path:
                            raw_data_paths.append(temp_path)
                            temp_files.append(temp_path)

                            # Check if this file can be analyzed
                            ext = Path(f.filename).suffix.lower()
                            if analyze_data and iv_analysis_available and ext in analyzable_extensions and not analyzed_file:
                                analyzed_file = temp_path

                if raw_data_paths:
                    files['raw_data'] = raw_data_paths

            # Perform IV analysis if enabled and we have an analyzable file
            if analyzed_file:
                analysis_result = analyze_iv_file(analyzed_file, component_id)

                if analysis_result['success']:
                    # Merge analyzed measurements (they take precedence over manual)
                    analyzed_measurements = analysis_result['measurements']

                    # Update measurements with analyzed values
                    measurements.update(analyzed_measurements)

                    # Generate and save the IV curve plot
                    if analysis_result['plot_bytes']:
                        # Save plot to temp file
                        fd, plot_temp_path = tempfile.mkstemp(suffix='.png')
                        os.close(fd)
                        with open(plot_temp_path, 'wb') as f:
                            f.write(analysis_result['plot_bytes'])
                        temp_files.append(plot_temp_path)
                        generated_plot_path = plot_temp_path

                        # Add to plot files
                        if 'plot' not in files:
                            files['plot'] = []
                        files['plot'].append(plot_temp_path)

                    # Build informative flash message
                    msg_parts = [f"Analyzed IV data: {analyzed_measurements.get('num_points', 0)} data points"]
                    msg_parts.append(f"Voltage range: {analyzed_measurements.get('voltage_min', 0):.0f} - {analyzed_measurements.get('voltage_max', 0):.0f} V")
                    msg_parts.append(f"Current @ max V: {analyzed_measurements.get('current_at_max_voltage', 0):.2e} A")
                    flash(". ".join(msg_parts), 'info')
                else:
                    flash(f"Could not analyze data file: {analysis_result['error']}", 'warning')

            # Create test result
            test_result = TestResult(
                component_id=component_id,
                test_type='iv_curve',
                pass_fail=pass_fail,
                measurements=measurements if measurements else None,
                files=files if files else None,
                tested_by=tested_by,
                test_setup=test_setup or None,
                test_conditions=test_conditions or None,
                notes=notes or None
            )

            test_id = test_result.save(g.db)

            # Build success message
            file_count = len(test_result.stored_files) if test_result.stored_files else 0
            msg = f'IV test recorded successfully (Test ID: {test_id})'
            if file_count > 0:
                msg += f' with {file_count} file(s)'
            flash(msg, 'success')

            return redirect(url_for('tests.test_detail', test_id=test_id))

        finally:
            # Clean up temp files
            for temp_path in temp_files:
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception:
                    pass

    # GET request - show the upload form
    components = Component.list_all(db=g.db)
    component_ids = [c.id for c in components]
    prefill_component_id = request.args.get('component_id', '')

    return render_template('upload/iv_test.html',
                         component_ids=component_ids,
                         prefill_component_id=prefill_component_id,
                         allowed_data_extensions=ALLOWED_DATA_EXTENSIONS,
                         iv_analysis_available=iv_analysis_available)


@upload_bp.route('/edge-imaging', methods=['GET', 'POST'])
def edge_imaging():
    """Upload an edge imaging analysis test result with automatic measurement extraction"""
    # Import OCR utilities (optional dependency)
    try:
        from hps_svt_tracker.image_analysis import (
            extract_measurements_from_multiple_images,
            measurements_to_test_format,
            check_ocr_available
        )
        ocr_available = check_ocr_available()
    except ImportError:
        ocr_available = False

    if request.method == 'POST':
        # Get form data
        component_id = request.form.get('component_id', '').strip()
        tested_by = request.form.get('tested_by', '').strip() or get_current_user()
        test_setup = request.form.get('test_setup', '').strip()
        test_conditions = request.form.get('test_conditions', '').strip()
        notes = request.form.get('notes', '').strip()
        extract_measurements = request.form.get('extract_measurements') == 'on'

        # Pass/fail
        pass_fail_value = request.form.get('pass_fail', '')
        pass_fail = None
        if pass_fail_value == 'pass':
            pass_fail = True
        elif pass_fail_value == 'fail':
            pass_fail = False

        # Manual measurements (can be overridden by OCR)
        edge_gap_mean = request.form.get('edge_gap_mean', '').strip()
        edge_gap_min = request.form.get('edge_gap_min', '').strip()
        edge_gap_max = request.form.get('edge_gap_max', '').strip()

        # Validate component exists
        if not component_id:
            flash('Component ID is required.', 'danger')
            return redirect(url_for('upload.edge_imaging'))

        component = Component.get(component_id, g.db)
        if not component:
            flash(f"Component '{component_id}' not found.", 'danger')
            return redirect(url_for('upload.edge_imaging'))

        # Build measurements dict from manual input
        measurements = {}
        if edge_gap_mean:
            try:
                measurements['edge_gap_mean'] = float(edge_gap_mean)
            except ValueError:
                flash('Edge gap mean must be a number.', 'danger')
                return redirect(url_for('upload.edge_imaging'))
        if edge_gap_min:
            try:
                measurements['edge_gap_min'] = float(edge_gap_min)
            except ValueError:
                flash('Edge gap min must be a number.', 'danger')
                return redirect(url_for('upload.edge_imaging'))
        if edge_gap_max:
            try:
                measurements['edge_gap_max'] = float(edge_gap_max)
            except ValueError:
                flash('Edge gap max must be a number.', 'danger')
                return redirect(url_for('upload.edge_imaging'))

        # Process file uploads
        files = {}
        temp_files = []  # Track temp files for cleanup
        image_temp_paths = []  # For OCR extraction
        original_filenames = {}  # Map temp paths to original filenames

        try:
            # Edge imaging files (images with embedded measurements)
            image_files = request.files.getlist('edge_images')
            if image_files:
                image_paths = []
                for f in image_files:
                    if f.filename != '':
                        if not allowed_image(f.filename):
                            flash(f"Invalid image file type: {f.filename}", 'warning')
                            continue
                        temp_path = save_temp_file(f)
                        if temp_path:
                            image_paths.append(temp_path)
                            temp_files.append(temp_path)
                            image_temp_paths.append(temp_path)
                            # Store original filename for position extraction
                            original_filenames[temp_path] = f.filename
                if image_paths:
                    files['image'] = image_paths

            # Attempt OCR measurement extraction if enabled and images provided
            ocr_result = None
            if extract_measurements and ocr_available and image_temp_paths:
                try:
                    ocr_result = extract_measurements_from_multiple_images(
                        image_temp_paths, original_filenames=original_filenames
                    )
                    if ocr_result.get('success_count', 0) > 0:
                        # Merge OCR measurements (they take precedence over manual)
                        ocr_measurements = measurements_to_test_format(ocr_result)
                        measurements.update(ocr_measurements)

                        # Build informative flash message
                        msg_parts = [f"Extracted measurements from {ocr_result['success_count']} image(s)"]
                        msg_parts.append(f"Found {ocr_result['overall_summary'].get('count', 0)} total measurement points")

                        # Mention per-image positions if any were detected
                        per_image = ocr_result.get('per_image_summary', {})
                        if per_image:
                            positions = sorted(per_image.keys())
                            msg_parts.append(f"Positions: {', '.join(positions)}")

                        flash(". ".join(msg_parts) + ".", 'info')
                    else:
                        flash("Could not extract measurements from images. "
                              "Manual measurements will be used.", 'warning')
                except Exception as e:
                    flash(f"OCR extraction failed: {str(e)}. Manual measurements will be used.", 'warning')

            # Create test result
            test_result = TestResult(
                component_id=component_id,
                test_type='edge_imaging',
                pass_fail=pass_fail,
                measurements=measurements if measurements else None,
                files=files if files else None,
                tested_by=tested_by,
                test_setup=test_setup or None,
                test_conditions=test_conditions or None,
                notes=notes or None
            )

            test_id = test_result.save(g.db)

            # Build success message
            file_count = len(test_result.stored_files) if test_result.stored_files else 0
            msg = f'Edge imaging test recorded successfully (Test ID: {test_id})'
            if file_count > 0:
                msg += f' with {file_count} file(s)'
            flash(msg, 'success')

            return redirect(url_for('tests.test_detail', test_id=test_id))

        finally:
            # Clean up temp files
            for temp_path in temp_files:
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception:
                    pass

    # GET request - show the upload form
    components = Component.list_all(db=g.db)
    component_ids = [c.id for c in components]
    prefill_component_id = request.args.get('component_id', '')

    return render_template('upload/edge_imaging.html',
                         component_ids=component_ids,
                         prefill_component_id=prefill_component_id,
                         allowed_image_extensions=ALLOWED_IMAGE_EXTENSIONS,
                         ocr_available=ocr_available)


def extract_images_from_tar(tar_file, temp_dir, data_input):
    """
    Extract image files from a tar archive.

    Args:
        tar_file: Werkzeug FileStorage object
        temp_dir: Directory to extract files to
        data_input: Label for the data input (J1, J3, or J5)

    Returns:
        List of tuples: (temp_path, metadata_dict) for each extracted image
    """
    images = []

    if not tar_file or tar_file.filename == '':
        return images

    # Save tar to temp first
    tar_temp_path = os.path.join(temp_dir, secure_filename(tar_file.filename))
    tar_file.save(tar_temp_path)

    try:
        with tarfile.open(tar_temp_path, mode='r:*') as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue

                # Check if it's an image file
                ext = Path(member.name).suffix.lower().lstrip('.')
                if ext not in ALLOWED_IMAGE_EXTENSIONS:
                    continue

                # Extract to temp directory
                # Use a safe filename to avoid path traversal
                safe_name = secure_filename(os.path.basename(member.name))
                if not safe_name:
                    continue

                # Create unique filename with data input prefix
                unique_name = f"{data_input}_{safe_name}"
                extract_path = os.path.join(temp_dir, unique_name)

                # Extract the file
                with tf.extractfile(member) as src:
                    if src:
                        with open(extract_path, 'wb') as dst:
                            dst.write(src.read())

                # Create metadata for this file
                metadata = {
                    'data_input': data_input,
                    'original_tar': tar_file.filename,
                    'original_name': os.path.basename(member.name)
                }

                images.append((extract_path, metadata))
    except tarfile.TarError as e:
        # Invalid tar file - will be handled by caller
        raise ValueError(f"Invalid tar file for {data_input}: {str(e)}")
    finally:
        # Clean up the tar file
        if os.path.exists(tar_temp_path):
            os.remove(tar_temp_path)

    return images


@upload_bp.route('/flange-qc', methods=['GET', 'POST'])
def flange_qc():
    """Upload a flange board QC test result with O20 plots for each data input (J1, J3, J5)"""
    if request.method == 'POST':
        # Get form data
        component_id = request.form.get('component_id', '').strip()
        tested_by = request.form.get('tested_by', '').strip() or get_current_user()
        feb_serial = request.form.get('feb_serial', '').strip()
        notes = request.form.get('notes', '').strip()

        # Pass/fail
        pass_fail_value = request.form.get('pass_fail', '')
        pass_fail = None
        if pass_fail_value == 'pass':
            pass_fail = True
        elif pass_fail_value == 'fail':
            pass_fail = False

        # Validate component exists and is a flange_board
        if not component_id:
            flash('Component ID is required.', 'danger')
            return redirect(url_for('upload.flange_qc'))

        component = Component.get(component_id, g.db)
        if not component:
            flash(f"Component '{component_id}' not found.", 'danger')
            return redirect(url_for('upload.flange_qc'))

        if component.type != 'flange_board':
            flash(f"Component '{component_id}' is not a flange board (type: {component.type}).", 'danger')
            return redirect(url_for('upload.flange_qc'))

        # Create temp directory for extraction
        temp_dir = tempfile.mkdtemp()

        try:
            # Process tar files for each data input
            all_files = []  # List of (path, metadata) tuples
            file_counts = {'J1': 0, 'J3': 0, 'J5': 0}

            for data_input in ['J1', 'J3', 'J5']:
                tar_field = f'{data_input.lower()}_tar'
                tar_file = request.files.get(tar_field)

                if tar_file and tar_file.filename != '':
                    try:
                        extracted = extract_images_from_tar(tar_file, temp_dir, data_input)
                        all_files.extend(extracted)
                        file_counts[data_input] = len(extracted)
                    except ValueError as e:
                        flash(str(e), 'warning')

            # Check if we have any files
            if not all_files:
                flash('No valid image files found in any of the tar files.', 'danger')
                return redirect(url_for('upload.flange_qc'))

            # Build measurements dict
            measurements = {
                'feb_serial': feb_serial,
                'j1_file_count': file_counts['J1'],
                'j3_file_count': file_counts['J3'],
                'j5_file_count': file_counts['J5']
            }

            # Prepare files dict for TestResult
            # We need to use a custom approach to attach metadata to each file
            plot_paths = [f[0] for f in all_files]
            file_metadata = {f[0]: f[1] for f in all_files}

            # Create test result
            test_result = TestResult(
                component_id=component_id,
                test_type='flange_qc_test',
                pass_fail=pass_fail,
                measurements=measurements,
                files={'plot': plot_paths} if plot_paths else None,
                tested_by=tested_by,
                notes=notes or None
            )

            # Store the file metadata for later use
            test_result._file_metadata = file_metadata

            test_id = test_result.save(g.db)

            # Now update the test_files records with metadata
            # Match files by their data_input prefix in the original_filename
            with g.db.get_connection() as conn:
                # Get all files for this test
                files = conn.execute("""
                    SELECT id, original_filename FROM test_files WHERE test_id = ?
                """, (test_id,)).fetchall()

                for file_row in files:
                    file_id = file_row['id']
                    original_filename = file_row['original_filename']

                    # Determine data_input from filename prefix (J1_, J3_, or J5_)
                    data_input = None
                    for di in ['J1', 'J3', 'J5']:
                        if original_filename.startswith(f"{di}_"):
                            data_input = di
                            # Get the original name without the prefix
                            orig_name = original_filename[len(f"{di}_"):]
                            break

                    if data_input:
                        # Find the matching metadata from the temp file
                        for temp_path, metadata in file_metadata.items():
                            if os.path.basename(temp_path) == original_filename:
                                conn.execute("""
                                    UPDATE test_files
                                    SET metadata_json = ?
                                    WHERE id = ?
                                """, (json.dumps(metadata), file_id))
                                break
                        else:
                            # If no exact match found, create metadata from filename
                            metadata = {
                                'data_input': data_input,
                                'original_name': orig_name
                            }
                            conn.execute("""
                                UPDATE test_files
                                SET metadata_json = ?
                                WHERE id = ?
                            """, (json.dumps(metadata), file_id))

                conn.commit()

            # Build success message
            total_files = sum(file_counts.values())
            msg = f'Flange QC test recorded (Test ID: {test_id}) with {total_files} plot(s): '
            msg += f"J1={file_counts['J1']}, J3={file_counts['J3']}, J5={file_counts['J5']}"
            flash(msg, 'success')

            return redirect(url_for('tests.test_detail', test_id=test_id))

        finally:
            # Clean up temp directory
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    # GET request - show the upload form
    # Filter to only show flange_board components
    components = Component.list_all(db=g.db)
    flange_components = [c for c in components if c.type == 'flange_board']
    component_ids = [c.id for c in flange_components]
    prefill_component_id = request.args.get('component_id', '')

    return render_template('upload/flange_qc.html',
                         component_ids=component_ids,
                         prefill_component_id=prefill_component_id)


@upload_bp.route('/maintenance', methods=['GET', 'POST'])
def maintenance():
    """Upload a maintenance log entry / comment for a component"""
    if request.method == 'POST':
        # Get form data
        component_id = request.form.get('component_id', '').strip()
        description = request.form.get('description', '').strip()
        log_type = request.form.get('log_type', 'note').strip()
        severity = request.form.get('severity', 'info').strip()
        logged_by = request.form.get('logged_by', '').strip() or get_current_user()

        # Validate required fields
        if not component_id:
            flash('Component ID is required.', 'danger')
            return redirect(url_for('upload.maintenance'))

        if not description:
            flash('Description/comment is required.', 'danger')
            return redirect(url_for('upload.maintenance'))

        # Validate component exists
        component = Component.get(component_id, g.db)
        if not component:
            flash(f"Component '{component_id}' not found.", 'danger')
            return redirect(url_for('upload.maintenance'))

        # Handle optional image upload
        image_rel_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                if not allowed_image(file.filename):
                    flash(f'Invalid image file type. Allowed: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}', 'danger')
                    return redirect(url_for('upload.maintenance'))

                # Create storage directory: data_dir/maintenance/component_id/
                maint_dir = os.path.join(g.db.data_dir, 'maintenance', component_id)
                os.makedirs(maint_dir, exist_ok=True)

                # Generate unique filename with timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                original_ext = Path(file.filename).suffix.lower()
                safe_filename = secure_filename(file.filename)
                base_name = Path(safe_filename).stem
                filename = f"{timestamp}_{base_name}{original_ext}"
                filepath = os.path.join(maint_dir, filename)

                # Save the file
                file.save(filepath)

                # Store relative path for database
                image_rel_path = os.path.relpath(filepath, g.db.data_dir)

        try:
            # Add maintenance log entry
            log_id = add_maintenance_log(
                component_id=component_id,
                description=description,
                log_type=log_type,
                severity=severity,
                logged_by=logged_by,
                image_path=image_rel_path,
                db=g.db
            )

            # Build success message
            msg = f'Comment added successfully for component {component_id}'
            if image_rel_path:
                msg += ' with attached image'
            flash(msg, 'success')
            return redirect(url_for('components.component_detail', component_id=component_id))

        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('upload.maintenance'))

    # GET request - show the upload form
    components = Component.list_all(db=g.db)
    component_ids = [c.id for c in components]
    prefill_component_id = request.args.get('component_id', '')

    return render_template('upload/maintenance.html',
                         component_ids=component_ids,
                         prefill_component_id=prefill_component_id,
                         allowed_image_extensions=ALLOWED_IMAGE_EXTENSIONS)


# Standard position options for the detector
LAYER_POSITIONS = []
# Layers 0-3: LayerN_{top/bottom}_{axial/stereo}
for layer in range(4):
    for tb in ['top', 'bottom']:
        for orientation in ['axial', 'stereo']:
            LAYER_POSITIONS.append(f"Layer{layer}_{tb}_{orientation}")

# Layers 4-7: LayerN_{top/bottom}_{axial/stereo}_{slot/hole}
for layer in range(4, 8):
    for tb in ['top', 'bottom']:
        for orientation in ['axial', 'stereo']:
            for position in ['slot', 'hole']:
                LAYER_POSITIONS.append(f"Layer{layer}_{tb}_{orientation}_{position}")

# FEB positions
FEB_POSITIONS = [f"FEB{i}" for i in range(1, 13)]

# Flange positions
FLANGE_POSITIONS = [f"Flange_slot{i}" for i in range(4)]


@upload_bp.route('/installation', methods=['GET', 'POST'])
def installation():
    """Record installation of a component"""
    if request.method == 'POST':
        # Get form data
        component_id = request.form.get('component_id', '').strip()
        position = request.form.get('position', '').strip()
        custom_position = request.form.get('custom_position', '').strip()
        run_period = request.form.get('run_period', '').strip()
        installed_by = request.form.get('installed_by', '').strip() or get_current_user()
        notes = request.form.get('notes', '').strip()

        # Use custom position if provided
        if custom_position:
            position = custom_position

        # Validate required fields
        if not component_id:
            flash('Component ID is required.', 'danger')
            return redirect(url_for('upload.installation'))

        if not position:
            flash('Position is required.', 'danger')
            return redirect(url_for('upload.installation'))

        if not run_period:
            flash('Run period is required.', 'danger')
            return redirect(url_for('upload.installation'))

        # Validate component exists
        component = Component.get(component_id, g.db)
        if not component:
            flash(f"Component '{component_id}' not found.", 'danger')
            return redirect(url_for('upload.installation'))

        # Check if component is already installed
        if component.installation_status == 'installed':
            flash(f"Component '{component_id}' is already installed at {component.installed_position}. "
                  "Remove it first before installing at a new position.", 'warning')
            return redirect(url_for('upload.installation'))

        try:
            install_component(
                component_id=component_id,
                position=position,
                run_period=run_period,
                installed_by=installed_by,
                notes=notes or None,
                db=g.db
            )

            flash(f"Component '{component_id}' installed at {position} for {run_period}.", 'success')
            return redirect(url_for('components.component_detail', component_id=component_id))

        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('upload.installation'))

    # GET request - show the form
    components = Component.list_all(db=g.db)
    # Filter to components that are not already installed
    available_components = [c for c in components if c.installation_status != 'installed']
    component_ids = [c.id for c in available_components]
    all_component_ids = [c.id for c in components]

    prefill_component_id = request.args.get('component_id', '')

    return render_template('upload/installation.html',
                         component_ids=component_ids,
                         all_component_ids=all_component_ids,
                         prefill_component_id=prefill_component_id,
                         layer_positions=LAYER_POSITIONS,
                         feb_positions=FEB_POSITIONS,
                         flange_positions=FLANGE_POSITIONS)

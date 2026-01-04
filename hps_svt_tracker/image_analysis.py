"""
Image analysis utilities for extracting measurements from microscope images.

This module provides OCR-based extraction of measurements from images
produced by microscope software (e.g., edge imaging analysis).
"""
import re
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

# Optional imports - gracefully handle missing dependencies
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


class MeasurementExtractionError(Exception):
    """Raised when measurement extraction fails"""
    pass


class OCRNotAvailableError(MeasurementExtractionError):
    """Raised when OCR dependencies are not installed"""
    pass


def check_ocr_available() -> bool:
    """
    Check if OCR dependencies are available.

    Returns:
        True if pytesseract and PIL are available
    """
    return PIL_AVAILABLE and TESSERACT_AVAILABLE


def extract_text_from_image(image_path: str,
                            config: str = '--psm 6') -> str:
    """
    Extract all text from an image using OCR.

    Args:
        image_path: Path to the image file
        config: Tesseract configuration string
               --psm 6: Assume a single uniform block of text
               --psm 3: Fully automatic page segmentation (default)
               --psm 11: Sparse text, find as much text as possible

    Returns:
        Extracted text from the image

    Raises:
        OCRNotAvailableError: If OCR dependencies are not installed
        FileNotFoundError: If image file doesn't exist
    """
    if not PIL_AVAILABLE:
        raise OCRNotAvailableError(
            "PIL/Pillow is required for image analysis. "
            "Install with: pip install Pillow"
        )
    if not TESSERACT_AVAILABLE:
        raise OCRNotAvailableError(
            "pytesseract is required for image analysis. "
            "Install with: pip install pytesseract\n"
            "Also ensure Tesseract OCR is installed on your system:\n"
            "  macOS: brew install tesseract\n"
            "  Ubuntu: sudo apt-get install tesseract-ocr\n"
            "  Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki"
        )

    if not Path(image_path).exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    img = Image.open(image_path)
    text = pytesseract.image_to_string(img, config=config)
    return text


def extract_measure_result_dialog(text: str) -> List[Dict[str, Any]]:
    """
    Parse measurements from a "Measure Result" dialog text.

    Expected format from microscope software:
    No.  Measure     Result
    1    2 Points    218.13 um
    2    2 Points    217.14 um

    Args:
        text: OCR-extracted text from the image

    Returns:
        List of measurement dicts with keys:
        - measurement_number: int
        - measurement_type: str (e.g., "2 Points")
        - value: float
        - unit: str (e.g., "um")
    """
    measurements = []

    # Pattern to match measurement lines with measurement number
    # Handles variations like: "1  2 Points  218.13 um" or "1 2Points 218.13um"
    # Also handles OCR artifacts like "2:" instead of "2" for the measurement number
    pattern_with_num = r'(\d+):?\s+(\d+\s*Points?)\s+([\d.]+)\s*(um|μm|mm|nm)?'

    # Pattern to match measurement lines WITHOUT measurement number
    # OCR sometimes misses or misreads the leading number (e.g., "1" becomes "|" or is dropped)
    # This pattern looks for "2 Points 123.45 um" without a leading measurement number
    pattern_without_num = r'(?<!\d)(\d+\s*Points?)\s+([\d.]+)\s*(um|μm|mm|nm)?'

    # First, find all matches with measurement numbers
    matches_with_num = re.findall(pattern_with_num, text, re.IGNORECASE)
    seen_values = set()

    for match in matches_with_num:
        num, measure_type, value, unit = match
        measurements.append({
            'measurement_number': int(num),
            'measurement_type': measure_type.strip(),
            'value': float(value),
            'unit': unit if unit else 'um'
        })
        seen_values.add(float(value))

    # Then, find matches without measurement numbers (to catch OCR misses)
    matches_without_num = re.findall(pattern_without_num, text, re.IGNORECASE)
    auto_num = len(measurements) + 1

    for match in matches_without_num:
        measure_type, value, unit = match
        val = float(value)
        # Only add if we haven't already seen this value (avoid duplicates)
        if val not in seen_values:
            measurements.append({
                'measurement_number': auto_num,
                'measurement_type': measure_type.strip(),
                'value': val,
                'unit': unit if unit else 'um'
            })
            seen_values.add(val)
            auto_num += 1

    # Sort by measurement number
    measurements.sort(key=lambda m: m['measurement_number'])

    return measurements


def extract_edge_measurements(image_path: str) -> Dict[str, Any]:
    """
    Extract edge imaging measurements from a microscope image.

    This is the main function for extracting measurements from
    edge imaging analysis images. It handles the "Measure Result"
    dialog box commonly embedded in microscope screenshots.

    Args:
        image_path: Path to the edge imaging analysis image

    Returns:
        Dict containing:
        - measurements: List of individual measurement dicts
        - summary: Dict with statistical summary (mean, min, max, count)
        - raw_text: The raw OCR text (for debugging)
        - success: Boolean indicating if extraction was successful
        - error: Error message if extraction failed

    Example:
        >>> result = extract_edge_measurements("sensor_edge.jpg")
        >>> print(result['summary'])
        {'mean': 221.95, 'min': 217.14, 'max': 230.58, 'count': 3}
    """
    result = {
        'measurements': [],
        'summary': {},
        'raw_text': '',
        'success': False,
        'error': None
    }

    try:
        # Extract text from image using multiple PSM modes
        # Different modes work better for different image layouts
        # Try all modes and use the one that finds the most measurements
        best_measurements = []
        best_text = ''

        for psm in [3, 4, 6, 11, 12]:  # Try various modes
            try:
                text = extract_text_from_image(image_path, config=f'--psm {psm}')
                measurements = extract_measure_result_dialog(text)

                # Keep the result with the most measurements
                if len(measurements) > len(best_measurements):
                    best_measurements = measurements
                    best_text = text

            except Exception:
                continue

        result['raw_text'] = best_text
        result['measurements'] = best_measurements

        if best_measurements:
            values = [m['value'] for m in best_measurements]
            result['summary'] = {
                'mean': round(sum(values) / len(values), 2),
                'min': min(values),
                'max': max(values),
                'count': len(values),
                'unit': best_measurements[0]['unit']
            }
            result['success'] = True
        else:
            result['error'] = "No measurements found in image"

    except OCRNotAvailableError as e:
        result['error'] = str(e)
    except Exception as e:
        result['error'] = f"Extraction failed: {str(e)}"

    return result


def extract_measurements_from_multiple_images(image_paths: List[str]) -> Dict[str, Any]:
    """
    Extract measurements from multiple edge imaging analysis images.

    Useful when multiple images are uploaded for a single test.

    Args:
        image_paths: List of paths to image files

    Returns:
        Dict containing:
        - images: Dict mapping image filename to its extraction result
        - all_measurements: Combined list of all measurements
        - overall_summary: Statistical summary across all images
        - success_count: Number of images successfully processed
        - error_count: Number of images that failed
    """
    result = {
        'images': {},
        'all_measurements': [],
        'overall_summary': {},
        'success_count': 0,
        'error_count': 0
    }

    all_values = []
    unit = 'um'

    for path in image_paths:
        filename = Path(path).name
        extraction = extract_edge_measurements(path)
        result['images'][filename] = extraction

        if extraction['success']:
            result['success_count'] += 1
            result['all_measurements'].extend(extraction['measurements'])
            all_values.extend([m['value'] for m in extraction['measurements']])
            if extraction['measurements']:
                unit = extraction['measurements'][0]['unit']
        else:
            result['error_count'] += 1

    if all_values:
        result['overall_summary'] = {
            'mean': round(sum(all_values) / len(all_values), 2),
            'min': min(all_values),
            'max': max(all_values),
            'count': len(all_values),
            'unit': unit
        }

    return result


def measurements_to_test_format(extraction_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert extraction results to the format expected by TestResult.

    This prepares the measurements dict for storage in the test_results table.

    Args:
        extraction_result: Result from extract_edge_measurements or
                          extract_measurements_from_multiple_images

    Returns:
        Dict suitable for TestResult.measurements parameter
    """
    measurements = {}

    # Get summary (either from single image or overall)
    summary = extraction_result.get('overall_summary') or extraction_result.get('summary', {})

    if summary:
        measurements['edge_gap_mean'] = summary.get('mean')
        measurements['edge_gap_min'] = summary.get('min')
        measurements['edge_gap_max'] = summary.get('max')
        measurements['edge_gap_count'] = summary.get('count')
        measurements['edge_gap_unit'] = summary.get('unit', 'um')

    # Include individual measurements for detailed analysis
    all_measurements = extraction_result.get('all_measurements') or extraction_result.get('measurements', [])
    if all_measurements:
        measurements['edge_gap_values'] = [m['value'] for m in all_measurements]

    # Include raw text for debugging/verification
    if extraction_result.get('raw_text'):
        measurements['ocr_raw_text'] = extraction_result['raw_text']

    return measurements

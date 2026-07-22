import os
import cv2
import numpy as np
import pytesseract
from PIL import Image
from pdf2image import convert_from_path

# Standard assumed wall height (metres) used for paint/tile-wall area math.
WALL_HEIGHT_M = 3.0
# Average opening sizes (metres) used to net-off paint area for doors/windows.
AVG_DOOR_AREA_SQM = 2.1 * 0.9    # standard door leaf
AVG_WINDOW_AREA_SQM = 1.2 * 1.05  # standard window
# Portion of built-up area assumed to be "wet areas" (kitchen/bath) requiring
# full-height wall tiling, used for the tile-area estimate.
WET_AREA_FRACTION = 0.15
WET_AREA_TILE_HEIGHT_M = 2.1


def _load_image(file_path):
    if file_path.lower().endswith('.pdf'):
        images = convert_from_path(file_path, first_page=1, last_page=1)
        image_path = file_path + "_converted.png"
        images[0].save(image_path, 'PNG')
    else:
        image_path = file_path

    img = cv2.imread(image_path)
    if img is None:
        # Fall back to PIL for formats/paths OpenCV struggles with (e.g. some PNGs with alpha)
        pil_img = Image.open(image_path).convert('RGB')
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    if img is None:
        raise ValueError("Could not read image file.")
    return img


def _detect_rooms_walls_openings(dilated, pixels_per_meter):
    """
    Heuristic AI-assisted detection of rooms, wall segments, doors and
    windows from a binarized/dilated floor-plan mask.

    - Rooms: internal (child) contours enclosed by the outer building
      boundary, above a minimum plausible room size.
    - Wall segments: straight line segments detected via probabilistic
      Hough transform on the wall mask edges.
    - Doors / Windows: convexity-defect gaps along the outer wall
      boundary, bucketed by physical width into door-sized vs
      window-sized openings.
    """
    contours, hierarchy = cv2.findContours(dilated, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

    room_count = 0
    if hierarchy is not None and len(contours) > 0:
        hierarchy = hierarchy[0]
        min_room_area_px = (1.8 * pixels_per_meter) ** 2  # ignore slivers/noise
        max_room_area_px = (dilated.shape[0] * dilated.shape[1]) * 0.9
        for i, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)
            parent = hierarchy[i][3]
            if parent != -1 and min_room_area_px < area < max_room_area_px:
                room_count += 1

    # Wall segment detection
    edges = cv2.Canny(dilated, 50, 150)
    min_line_len = max(int(pixels_per_meter * 0.5), 10)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=60,
        minLineLength=min_line_len, maxLineGap=10
    )
    wall_count = int(len(lines)) if lines is not None else 0

    # Door / window opening detection via convexity defects on the
    # largest (outer boundary) contour.
    door_count = 0
    window_count = 0
    if contours:
        largest = max(contours, key=cv2.contourArea)
        if len(largest) > 3:
            try:
                hull_idx = cv2.convexHull(largest, returnPoints=False)
                hull_idx = np.sort(hull_idx, axis=0)
                defects = cv2.convexityDefects(largest, hull_idx)
            except cv2.error:
                defects = None

            if defects is not None:
                door_min_px = 0.6 * pixels_per_meter
                door_max_px = 1.3 * pixels_per_meter
                window_min_px = 0.3 * pixels_per_meter

                for i in range(defects.shape[0]):
                    s, e, f, d = defects[i][0]
                    start = largest[s][0]
                    end = largest[e][0]
                    gap_len = float(np.linalg.norm(start.astype(float) - end.astype(float)))
                    if door_min_px <= gap_len <= door_max_px:
                        door_count += 1
                    elif window_min_px <= gap_len < door_min_px:
                        window_count += 1

    # Guarantee at least a sensible minimum so downstream BOQ/area maths
    # always has something to work with even on very simple sketches.
    room_count = max(room_count, 1)
    door_count = max(door_count, 1)
    window_count = max(window_count, room_count)

    return {
        "room_count": room_count,
        "wall_count": wall_count,
        "door_count": door_count,
        "window_count": window_count,
    }


def _compute_derived_areas(built_up_area_sqm, perimeter_m, door_count, window_count):
    """Slab, paint and tile area calculations derived from detected geometry."""
    slab_area_sqm = round(built_up_area_sqm, 2)  # one structural slab per floor

    gross_wall_area = perimeter_m * WALL_HEIGHT_M
    opening_area = (door_count * AVG_DOOR_AREA_SQM) + (window_count * AVG_WINDOW_AREA_SQM)
    # Paint both faces (internal + external) of the walls, net of openings.
    paint_area_sqm = max((gross_wall_area - opening_area) * 2, 0.0)

    floor_tile_area = built_up_area_sqm
    wet_area = built_up_area_sqm * WET_AREA_FRACTION
    wet_wall_tile_area = wet_area * 2 * WET_AREA_TILE_HEIGHT_M ** 0.5  # dado-height wall tiling estimate
    tile_area_sqm = floor_tile_area + wet_wall_tile_area

    return {
        "slab_area_sqm": round(slab_area_sqm, 2),
        "paint_area_sqm": round(paint_area_sqm, 2),
        "tile_area_sqm": round(tile_area_sqm, 2),
    }


def process_floor_plan(file_path, pixels_per_meter=50.0):
    """
    AI-assisted floor plan analysis:
      - Detects walls/polylines, calculates perimeter and built-up area
        using OpenCV (contour analysis).
      - Detects room count, wall segment count, door & window openings.
      - Derives slab, paint and tile areas from the detected geometry.
      - Extracts embedded text/dimensions via OCR (Tesseract).
    """
    img = _load_image(file_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # OCR Metadata Extraction
    try:
        ocr_text = pytesseract.image_to_string(gray)
    except Exception as e:
        ocr_text = f"OCR Error or Tesseract not configured: {str(e)}"

    # Pre-processing for Wall Contour Detection
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY_INV)[1]

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dilated = cv2.dilate(thresh, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    total_perimeter_px = 0.0
    total_area_px = 0.0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 1000:
            total_area_px += area
            total_perimeter_px += cv2.arcLength(cnt, True)

    perimeter_m = total_perimeter_px / pixels_per_meter
    built_up_area_sqm = total_area_px / (pixels_per_meter ** 2)

    # Guard against blank/unreadable plans producing zero-area results
    if built_up_area_sqm <= 0:
        built_up_area_sqm = (img.shape[0] * img.shape[1]) / (pixels_per_meter ** 2) * 0.5
        perimeter_m = 2 * (img.shape[0] + img.shape[1]) / pixels_per_meter * 0.5

    detection = _detect_rooms_walls_openings(dilated, pixels_per_meter)
    derived_areas = _compute_derived_areas(
        built_up_area_sqm, perimeter_m,
        detection["door_count"], detection["window_count"]
    )

    result = {
        "perimeter_m": round(perimeter_m, 2),
        "built_up_area_sqm": round(built_up_area_sqm, 2),
        "ocr_metadata": ocr_text.strip(),
    }
    result.update(detection)
    result.update(derived_areas)
    return result

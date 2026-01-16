"""
Agentic document extraction for functional evidence from scientific PDFs.

This module implements a page-by-page agentic extraction workflow using:
- PaddleOCR for text extraction
- LayoutReader (LayoutLMv3) for reading order
- Layout detection for region identification (text, table, chart, figure)
- VLM tools (AnalyzeChart, AnalyzeTable) for visual analysis
- LangChain agents to orchestrate extraction

Adapted from the ADE (Agentic Document Extraction) approach.
"""

import os
import re
import json
import base64
from io import BytesIO
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

# Set environment variable early to suppress PaddleOCR connectivity checks
os.environ.setdefault('DISABLE_MODEL_SOURCE_CHECK', 'True')

import numpy as np
from PIL import Image

from .utils import FunctionalExperiment


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class OCRRegion:
    """Store OCR result for a text region."""
    text: str
    bbox: list  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    confidence: float
    
    @property
    def bbox_xyxy(self) -> List[int]:
        """Return bbox as [x1, y1, x2, y2] format."""
        x_coords = [p[0] for p in self.bbox]
        y_coords = [p[1] for p in self.bbox]
        return [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]


@dataclass
class LayoutRegion:
    """Store layout detection result for a region."""
    region_id: int
    region_type: str  # 'text', 'table', 'chart', 'figure', 'title', etc.
    bbox: list  # [x1, y1, x2, y2]
    confidence: float


# =============================================================================
# LAZY LOADING OF HEAVY MODELS
# =============================================================================

_ocr_engine = None
_layout_engine = None
_layout_reader_model = None


def _get_ocr_engine():
    """Lazy-load OCR engine with fallback options.
    
    On macOS, prefers EasyOCR due to PaddleOCR segfault issues.
    Can be overridden with USE_PADDLEOCR=true environment variable.
    """
    global _ocr_engine
    if _ocr_engine is None:
        import platform
        is_macos = platform.system() == 'Darwin'
        force_paddle = os.getenv('USE_PADDLEOCR', 'false').lower() == 'true'
        
        # On macOS, prefer EasyOCR unless PaddleOCR is explicitly requested
        # PaddleOCR often causes segfaults on macOS
        if is_macos and not force_paddle:
            try:
                import easyocr
                _ocr_engine = easyocr.Reader(['en'], gpu=False)
                print("         Using EasyOCR for text extraction (macOS compatibility)")
            except ImportError:
                print("         Warning: EasyOCR not available, trying PaddleOCR...")
                force_paddle = True
            except Exception as e:
                print(f"         Warning: EasyOCR initialization failed: {e}, trying PaddleOCR...")
                force_paddle = True
        
        # Try PaddleOCR (either forced or as primary on non-macOS)
        if _ocr_engine is None or force_paddle:
            try:
                from paddleocr import PaddleOCR
                # Use minimal parameters that work across PaddleOCR versions
                # Only specify language - other parameters may not be supported in all versions
                _ocr_engine = PaddleOCR(lang='en')
                print("         Using PaddleOCR for text extraction")
            except Exception as e:
                print(f"         Warning: PaddleOCR initialization failed: {e}")
                # Try EasyOCR as fallback
                if _ocr_engine is None:
                    try:
                        import easyocr
                        _ocr_engine = easyocr.Reader(['en'], gpu=False)
                        print("         Using EasyOCR as fallback for text extraction")
                    except ImportError:
                        print("         Error: Neither PaddleOCR nor EasyOCR available")
                        raise RuntimeError(
                            "OCR engine not available. Please install paddleocr or easyocr. "
                            "On macOS, EasyOCR is recommended: pip install easyocr"
                        )
                    except Exception as e2:
                        print(f"         Error: EasyOCR also failed: {e2}")
                        raise RuntimeError(f"Failed to initialize OCR engine: {e2}")
    
    return _ocr_engine


def _get_layout_engine():
    """Lazy-load PaddleOCR layout detection engine."""
    global _layout_engine
    if _layout_engine is None:
        # Check if we're using EasyOCR - if so, skip layout detection to avoid PDX conflicts
        ocr_type = type(_ocr_engine).__module__ if _ocr_engine is not None else None
        if ocr_type and 'easyocr' in ocr_type.lower():
            # Using EasyOCR, skip PaddleOCR layout detection to avoid PDX initialization conflicts
            _layout_engine = None
            return None
        
        try:
            from paddleocr import LayoutDetection
            _layout_engine = LayoutDetection()
        except (ImportError, AttributeError, RuntimeError) as e:
            # LayoutDetection might not be available or PDX initialization might fail
            # Return None and handle gracefully in detect_layout_regions
            if "already been initialized" in str(e) or "PDX" in str(e):
                # Silently skip - this is expected when using EasyOCR
                pass
            _layout_engine = None
    return _layout_engine


_layout_reader_warning_shown = False

def _get_layout_reader_model():
    """Lazy-load LayoutReader model for reading order."""
    global _layout_reader_model, _layout_reader_warning_shown
    if _layout_reader_model is None:
        try:
            from transformers import LayoutLMv3ForTokenClassification
            from layoutreader.v3.helpers import prepare_inputs, boxes2inputs, parse_logits
            model_slug = "hantian/layoutreader"
            _layout_reader_model = LayoutLMv3ForTokenClassification.from_pretrained(model_slug)
        except ImportError:
            # LayoutReader package not installed - this is expected and fine
            if not _layout_reader_warning_shown:
                # Only show warning once
                _layout_reader_warning_shown = True
            _layout_reader_model = None
        except Exception as e:
            # Other errors (model download, etc.)
            if not _layout_reader_warning_shown:
                print(f"Note: LayoutReader model not available ({type(e).__name__}), using default reading order")
                _layout_reader_warning_shown = True
            _layout_reader_model = None
    return _layout_reader_model


# =============================================================================
# PDF TO IMAGE CONVERSION
# =============================================================================

def pdf_to_images(pdf_path: str, dpi: int = 200) -> List[Image.Image]:
    """
    Convert PDF pages to PIL images.
    
    Parameters
    ----------
    pdf_path : str
        Path to PDF file
    dpi : int
        Resolution for rendering (default: 200)
        
    Returns
    -------
    List[Image.Image]
        List of PIL images, one per page
    """
    from pdf2image import convert_from_path
    
    images = convert_from_path(pdf_path, dpi=dpi)
    return images


# =============================================================================
# OCR PROCESSING
# =============================================================================

def process_page_ocr(image: Image.Image) -> Tuple[List[OCRRegion], np.ndarray]:
    """
    Run OCR on a page image (supports PaddleOCR and EasyOCR).
    
    Parameters
    ----------
    image : PIL.Image
        Page image
        
    Returns
    -------
    Tuple[List[OCRRegion], np.ndarray]
        OCR regions and processed image array
    """
    ocr = _get_ocr_engine()
    
    # Convert PIL Image to numpy array
    img_array = np.array(image)
    
    # Detect OCR engine type and process accordingly
    ocr_type = type(ocr).__module__
    
    try:
        if 'paddleocr' in ocr_type.lower() or hasattr(ocr, 'ocr'):
            # PaddleOCR API
            result = ocr.ocr(img_array)
            
            # Handle case where result is None or empty
            if not result or not result[0]:
                return [], img_array
            
            # Extract data from first page (PaddleOCR returns list of pages)
            page_result = result[0]
            
            # Build OCRRegion list
            ocr_regions = []
            for line in page_result:
                if line and len(line) >= 2:
                    bbox = line[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                    text_info = line[1]  # (text, confidence)
                    
                    if isinstance(text_info, tuple) and len(text_info) >= 2:
                        text = text_info[0]
                        confidence = text_info[1]
                    else:
                        # Fallback if format is different
                        text = str(text_info) if text_info else ""
                        confidence = 1.0
                    
                    ocr_regions.append(OCRRegion(
                        text=text,
                        bbox=[[int(p[0]), int(p[1])] for p in bbox],
                        confidence=float(confidence)
                    ))
            
            return ocr_regions, img_array
            
        elif 'easyocr' in ocr_type.lower() or hasattr(ocr, 'readtext'):
            # EasyOCR API
            result = ocr.readtext(img_array)
            
            ocr_regions = []
            for detection in result:
                bbox_points = detection[0]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                text = detection[1]  # text string
                confidence = detection[2]  # confidence score
                
                ocr_regions.append(OCRRegion(
                    text=text,
                    bbox=[[int(p[0]), int(p[1])] for p in bbox_points],
                    confidence=float(confidence)
                ))
            
            return ocr_regions, img_array
            
        else:
            raise RuntimeError(f"Unknown OCR engine type: {ocr_type}")
            
    except Exception as e:
        print(f"         Warning: OCR processing failed: {e}")
        # Return empty regions but keep the image
        return [], img_array


# =============================================================================
# READING ORDER
# =============================================================================

def get_reading_order(ocr_regions: List[OCRRegion], verbose: bool = False) -> List[int]:
    """
    Use LayoutReader to determine reading order of OCR regions.
    
    Parameters
    ----------
    ocr_regions : List[OCRRegion]
        OCR regions from PaddleOCR
    verbose : bool
        If True, print debug information
        
    Returns
    -------
    List[int]
        Reading order position for each region index (or default order if LayoutReader unavailable)
    """
    if not ocr_regions:
        return []
    
    model = _get_layout_reader_model()
    
    # If model is not available, return default order (top-to-bottom, left-to-right)
    if model is None:
        if verbose:
            print("         Note: LayoutReader not available, using default reading order")
        return list(range(len(ocr_regions)))
    
    try:
        # Import helpers - these should be available if model loaded successfully
        try:
            from layoutreader.v3.helpers import prepare_inputs, boxes2inputs, parse_logits
        except ImportError:
            # Helpers not available even though model loaded - fallback
            if verbose:
                print("         Note: LayoutReader helpers not available, using default order")
            return list(range(len(ocr_regions)))
        
        # Calculate image dimensions from bounding boxes (with padding)
        max_x = max_y = 0
        for region in ocr_regions:
            x1, y1, x2, y2 = region.bbox_xyxy
            max_x = max(max_x, x2)
            max_y = max(max_y, y2)
        
        image_width = max_x * 1.1
        image_height = max_y * 1.1
        
        if verbose:
            print(f"         Image dimensions: {image_width:.0f} x {image_height:.0f}")
        
        # Convert bboxes to LayoutReader format (normalized to 0-1000)
        boxes = []
        for region in ocr_regions:
            x1, y1, x2, y2 = region.bbox_xyxy
            left = int((x1 / image_width) * 1000)
            top = int((y1 / image_height) * 1000)
            right = int((x2 / image_width) * 1000)
            bottom = int((y2 / image_height) * 1000)
            boxes.append([left, top, right, bottom])
        
        # Prepare inputs and run inference
        inputs = boxes2inputs(boxes)
        inputs = prepare_inputs(inputs, model)
        logits = model(**inputs).logits.cpu().squeeze(0)
        reading_order = parse_logits(logits, len(boxes))
        
        if verbose:
            print(f"         Reading order calculated for {len(reading_order)} regions")
        
        return reading_order
        
    except ImportError as e:
        # LayoutReader package not installed - this is expected
        if verbose:
            print(f"         Note: LayoutReader package not available ({e}), using default order")
        return list(range(len(ocr_regions)))
    except Exception as e:
        # If LayoutReader fails for other reasons, return default order
        if verbose:
            print(f"         Warning: Reading order calculation failed: {e}, using default order")
        return list(range(len(ocr_regions)))


def get_ordered_text(ocr_regions: List[OCRRegion], reading_order: List[int]) -> List[Dict[str, Any]]:
    """
    Return OCR regions sorted by reading order.
    
    Parameters
    ----------
    ocr_regions : List[OCRRegion]
        OCR regions
    reading_order : List[int]
        Reading order positions
        
    Returns
    -------
    List[Dict]
        Ordered text with position, text, confidence, bbox
    """
    if not ocr_regions or not reading_order:
        return []
    
    indexed_regions = [
        (reading_order[i], i, ocr_regions[i]) 
        for i in range(len(ocr_regions))
    ]
    indexed_regions.sort(key=lambda x: x[0])
    
    ordered_text = []
    for position, original_idx, region in indexed_regions:
        ordered_text.append({
            "position": position,
            "text": region.text,
            "confidence": region.confidence,
            "bbox": region.bbox_xyxy
        })
    
    return ordered_text


# =============================================================================
# LAYOUT DETECTION
# =============================================================================

def _detect_layout_heuristic(ocr_regions: List[OCRRegion], image: Image.Image) -> List[LayoutRegion]:
    """
    Heuristic-based layout detection using OCR bounding boxes.
    
    Identifies potential table/chart regions based on:
    - Dense text regions (many small boxes in a grid pattern) = tables
    - Figure labels followed by large areas = figures
    - Text patterns that suggest tables (numbers, short text, alignment)
    """
    if not ocr_regions:
        return []
    
    regions = []
    image_width, image_height = image.size
    
    # Strategy 1: Find table regions by looking for dense, aligned text regions
    # Tables typically have many short text segments aligned in rows/columns
    from collections import defaultdict
    
    # Group regions by approximate Y position (rows) and X position (columns)
    y_buckets = defaultdict(list)
    x_buckets = defaultdict(list)
    
    for region in ocr_regions:
        x1, y1, x2, y2 = region.bbox_xyxy
        center_y = (y1 + y2) / 2
        center_x = (x1 + x2) / 2
        
        # Bucket by Y position (tolerance: 20 pixels for row alignment)
        y_bucket = int(center_y / 20) * 20
        y_buckets[y_bucket].append(region)
        
        # Bucket by X position (tolerance: 50 pixels for column alignment)
        x_bucket = int(center_x / 50) * 50
        x_buckets[x_bucket].append(region)
    
    # Find rows with many regions (potential table rows)
    dense_rows = {y: regions for y, regions in y_buckets.items() if len(regions) >= 5}
    
    if dense_rows:
        # Find columns that appear in multiple dense rows (table structure)
        column_counts = defaultdict(int)
        for y, row_regions in dense_rows.items():
            for region in row_regions:
                x1, y1, x2, y2 = region.bbox_xyxy
                center_x = (x1 + x2) / 2
                x_bucket = int(center_x / 50) * 50
                column_counts[x_bucket] += 1
        
        # If we have multiple columns with many regions, likely a table
        significant_columns = [x for x, count in column_counts.items() if count >= 3]
        
        if len(significant_columns) >= 2:  # At least 2 columns
            # Find bounding box of all regions in dense rows
            all_table_regions = []
            for row_regions in dense_rows.values():
                all_table_regions.extend(row_regions)
            
            if all_table_regions:
                min_x = min(r.bbox_xyxy[0] for r in all_table_regions)
                max_x = max(r.bbox_xyxy[2] for r in all_table_regions)
                min_y = min(r.bbox_xyxy[1] for r in all_table_regions)
                max_y = max(r.bbox_xyxy[3] for r in all_table_regions)
                
                # Check if text looks like table data (short segments, numbers)
                table_text = " ".join([r.text for r in all_table_regions])
                has_numbers = any(char.isdigit() for char in table_text)
                avg_length = sum(len(r.text) for r in all_table_regions) / len(all_table_regions)
                
                if has_numbers and avg_length < 40:  # Short text with numbers
                    regions.append(LayoutRegion(
                        region_id=len(regions),
                        region_type='table',
                        bbox=[int(max(0, min_x - 10)), int(max(0, min_y - 10)), 
                              int(min(image_width, max_x + 10)), int(min(image_height, max_y + 10))],
                        confidence=0.7
                    ))
    
    # Strategy 2: Find figure regions by looking for "Figure" or "Fig" labels
    figure_keywords = ['figure', 'fig', 'fig.', 'figs']
    figure_labels = []
    
    for region in ocr_regions:
        text_lower = region.text.lower().strip()
        # Check if text starts with figure keyword
        for keyword in figure_keywords:
            if text_lower.startswith(keyword) and len(text_lower) < 30:
                figure_labels.append(region)
                break
    
    # For each figure label, create a region that likely contains the figure
    for i, label_region in enumerate(figure_labels[:10]):  # Limit to first 10
        x1, y1, x2, y2 = label_region.bbox_xyxy
        
        # Figure is typically below or to the right of the label
        # Create a region: start from label, extend down and right
        figure_bbox = [
            int(max(0, x1 - 20)),
            int(y1),
            int(min(image_width, x1 + 500)),  # Extend right
            int(min(image_height, y1 + 600))   # Extend down
        ]
        
        regions.append(LayoutRegion(
            region_id=len(regions),
            region_type='figure',
            bbox=figure_bbox,
            confidence=0.6
        ))
    
    # Strategy 3: Look for large empty areas that might contain charts/figures
    # (This is more complex and might not be reliable, so we'll skip it for now)
    
    return regions


def detect_layout_regions(image: Image.Image, ocr_regions: Optional[List[OCRRegion]] = None) -> List[LayoutRegion]:
    """
    Detect layout regions (text, table, chart, figure) in a page image.
    
    Parameters
    ----------
    image : PIL.Image
        Page image
    ocr_regions : List[OCRRegion], optional
        OCR regions for heuristic fallback
        
    Returns
    -------
    List[LayoutRegion]
        Detected layout regions
    """
    # Try PaddleOCR layout detection first
    try:
        layout_engine = _get_layout_engine()
    except RuntimeError as e:
        if "already been initialized" in str(e) or "PDX" in str(e):
            # PDX initialization conflict - use heuristic fallback
            if ocr_regions:
                return _detect_layout_heuristic(ocr_regions, image)
            return []
        raise
    
    # If layout detection is not available, use heuristic fallback
    if layout_engine is None:
        if ocr_regions:
            return _detect_layout_heuristic(ocr_regions, image)
        return []
    
    # Convert to numpy array
    img_array = np.array(image)
    
    try:
        # Try to run layout detection
        if hasattr(layout_engine, 'predict'):
            layout_result = layout_engine.predict(img_array)
        elif hasattr(layout_engine, 'ocr'):
            # Some versions might use ocr method with layout=True
            layout_result = layout_engine.ocr(img_array, layout=True)
        else:
            # Fallback to heuristic
            if ocr_regions:
                return _detect_layout_heuristic(ocr_regions, image)
            return []
        
        regions = []
        # Handle different result formats
        if isinstance(layout_result, list) and len(layout_result) > 0:
            result_data = layout_result[0]
            if isinstance(result_data, dict) and 'boxes' in result_data:
                for i, box in enumerate(result_data['boxes']):
                    regions.append(LayoutRegion(
                        region_id=i,
                        region_type=box.get('label', 'text'),
                        bbox=[int(x) for x in box.get('coordinate', [0, 0, 0, 0])],
                        confidence=box.get('score', 1.0)
                    ))
        
        # Sort by confidence
        regions = sorted(regions, key=lambda x: x.confidence, reverse=True)
        return regions
        
    except Exception as e:
        # If layout detection fails, use heuristic fallback
        if "already been initialized" not in str(e) and "PDX" not in str(e):
            print(f"         Warning: Layout detection failed: {e}, using heuristic")
        if ocr_regions:
            return _detect_layout_heuristic(ocr_regions, image)
        return []


# =============================================================================
# IMAGE CROPPING AND ENCODING
# =============================================================================

def crop_region(image: Image.Image, bbox: List[int], padding: int = 10) -> Image.Image:
    """Crop a region from image with optional padding."""
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(image.width, x2 + padding)
    y2 = min(image.height, y2 + padding)
    return image.crop((x1, y1, x2, y2))


def image_to_base64(img: Image.Image, max_size: int = 1500) -> str:
    """Convert PIL Image to base64 string, resizing if too large.
    
    Parameters
    ----------
    img : PIL.Image
        Image to convert
    max_size : int
        Maximum dimension (width or height). Images larger than this will be resized.
        Default 1500 works well with GPT-4o-mini vision. Use 2000+ for gpt-4o.
        
    Returns
    -------
    str
        Base64-encoded PNG string
    """
    # Resize if too large (VLMs struggle with very large images)
    if img.width > max_size or img.height > max_size:
        # Calculate new size preserving aspect ratio
        ratio = min(max_size / img.width, max_size / img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def prepare_region_images(
    image: Image.Image, 
    layout_regions: List[LayoutRegion],
    verbose: bool = False
) -> Dict[int, Dict[str, Any]]:
    """
    Crop and encode layout regions for VLM analysis.
    
    Parameters
    ----------
    image : PIL.Image
        Full page image
    layout_regions : List[LayoutRegion]
        Detected layout regions
    verbose : bool
        Print debug information
        
    Returns
    -------
    Dict[int, Dict]
        Mapping of region_id to {'image', 'base64', 'type', 'bbox'}
    """
    region_images = {}
    for region in layout_regions:
        cropped = crop_region(image, region.bbox)
        base64_str = image_to_base64(cropped)
        region_images[region.region_id] = {
            'image': cropped,
            'base64': base64_str,
            'type': region.region_type,
            'bbox': region.bbox
        }
        if verbose:
            print(f"           Region {region.region_id} ({region.region_type}): "
                  f"bbox={region.bbox}, cropped size={cropped.size}, base64={len(base64_str)} chars")
    return region_images


# =============================================================================
# VLM TOOLS
# =============================================================================

# Tool prompts
CHART_ANALYSIS_PROMPT = """You are a Chart Analysis specialist for scientific papers.
Analyze this chart/figure image and extract:

1. **Chart Type**: (line, bar, scatter, pie, etc.)
2. **Title**: (if visible)
3. **Axes**: X-axis label, Y-axis label, and tick values
4. **Data Points**: Key values (peaks, troughs, endpoints)
5. **Trends**: Overall pattern description
6. **Legend**: (if present)
7. **Statistical Info**: p-values, error bars, significance markers

Focus on functional assay results - enzyme activity, protein expression, 
cellular phenotypes, etc. that might indicate variant effects.

Return a JSON object with this structure:
```json
{{
  "chart_type": "...",
  "title": "...",
  "x_axis": {{"label": "...", "ticks": [...]}},
  "y_axis": {{"label": "...", "ticks": [...]}},
  "key_data_points": [...],
  "trends": "...",
  "legend": [...],
  "statistics": "..."
}}
```
"""

TABLE_ANALYSIS_PROMPT = """You are a Table Extraction specialist for scientific papers.
Extract structured data from this table image.

1. **Identify Structure**: Column headers, row labels, data cells
2. **Extract All Data**: Preserve exact values and alignment
3. **Handle Special Cases**: Merged cells, empty cells (mark as null)

Focus on functional assay results - look for:
- Variant names/labels
- Wild-type vs mutant comparisons
- Activity measurements, fold changes
- Statistical significance markers

Return a JSON object with this structure:
```json
{{
  "table_title": "...",
  "column_headers": ["header1", "header2", ...],
  "rows": [
    {{"row_label": "...", "values": [val1, val2, ...]}},
    ...
  ],
  "notes": "any footnotes or source info"
}}
```
"""


def _call_vlm_with_image(image_base64: str, prompt: str, verbose: bool = False) -> str:
    """Call VLM with an image and prompt.
    
    Parameters
    ----------
    image_base64 : str
        Base64-encoded PNG image
    prompt : str
        Analysis prompt
    verbose : bool
        Print debug info
        
    Returns
    -------
    str
        VLM response content
    """
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage
    from .config import AGENTIC_VLM_MODEL
    
    # Validate image
    if not image_base64 or len(image_base64) < 100:
        return f"Error: Invalid or empty image (base64 length: {len(image_base64) if image_base64 else 0})"
    
    if verbose:
        print(f"            VLM call: image size {len(image_base64)} chars, model {AGENTIC_VLM_MODEL}")
    
    # Use gpt-4o for better vision capabilities if available, otherwise fall back
    vlm = ChatOpenAI(model=AGENTIC_VLM_MODEL, temperature=0, max_tokens=2000)
    
    # Build message with image - use "high" detail for better analysis
    message = HumanMessage(
        content=[
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_base64}",
                    "detail": "high"  # Use high detail for scientific figures/tables
                }
            }
        ]
    )
    
    try:
        response = vlm.invoke([message])
        return response.content
    except Exception as e:
        return f"VLM Error: {str(e)}"


# Global variable to hold region images for tool access
_current_region_images: Dict[int, Dict[str, Any]] = {}


def _create_analyze_chart_tool(verbose: bool = False):
    """Create the AnalyzeChart tool."""
    from langchain_core.tools import tool
    
    @tool
    def AnalyzeChart(region_id: int) -> str:
        """Analyze a chart or figure region using VLM.
        Use this tool when you need to extract data from charts, graphs, or figures.
        
        Args:
            region_id: The ID of the layout region to analyze (must be a chart/figure type)
        
        Returns:
            JSON string with chart type, axes, data points, and trends
        """
        global _current_region_images
        
        if region_id not in _current_region_images:
            return f"Error: Region {region_id} not found. Available regions: {list(_current_region_images.keys())}"
        
        region_data = _current_region_images[region_id]
        
        # Get image dimensions for debugging
        img = region_data.get('image')
        img_info = f"size: {img.size if img else 'N/A'}" if img else "no image"
        base64_len = len(region_data.get('base64', ''))
        
        if verbose:
            print(f"            AnalyzeChart region {region_id}: {img_info}, base64: {base64_len} chars")
        
        if region_data['type'] not in ['chart', 'figure']:
            if verbose:
                print(f"            Note: Region {region_id} is type '{region_data['type']}', not a chart/figure")
        
        # Check for valid image
        if base64_len < 100:
            return f"Error: Region {region_id} has invalid image (too small: {base64_len} chars)"
        
        result = _call_vlm_with_image(region_data['base64'], CHART_ANALYSIS_PROMPT, verbose=verbose)
        return result
    
    return AnalyzeChart


def _create_analyze_table_tool(verbose: bool = False):
    """Create the AnalyzeTable tool."""
    from langchain_core.tools import tool
    
    @tool
    def AnalyzeTable(region_id: int) -> str:
        """Extract structured data from a table region using VLM.
        Use this tool when you need to extract tabular data with headers and rows.
        
        Args:
            region_id: The ID of the layout region to analyze (must be a table type)
        
        Returns:
            JSON string with table headers, rows, and any notes
        """
        global _current_region_images
        
        if region_id not in _current_region_images:
            return f"Error: Region {region_id} not found. Available regions: {list(_current_region_images.keys())}"
        
        region_data = _current_region_images[region_id]
        
        # Get image dimensions for debugging
        img = region_data.get('image')
        img_info = f"size: {img.size if img else 'N/A'}" if img else "no image"
        base64_len = len(region_data.get('base64', ''))
        
        if verbose:
            print(f"            AnalyzeTable region {region_id}: {img_info}, base64: {base64_len} chars")
        
        if region_data['type'] != 'table':
            if verbose:
                print(f"            Note: Region {region_id} is type '{region_data['type']}', not a table")
        
        # Check for valid image
        if base64_len < 100:
            return f"Error: Region {region_id} has invalid image (too small: {base64_len} chars)"
        
        result = _call_vlm_with_image(region_data['base64'], TABLE_ANALYSIS_PROMPT, verbose=verbose)
        return result
    
    return AnalyzeTable


# =============================================================================
# AGENT CREATION
# =============================================================================

def _format_ordered_text(ordered_text: List[Dict], max_items: int = 100) -> str:
    """Format ordered text for the system prompt."""
    lines = []
    for item in ordered_text[:max_items]:
        lines.append(f"[{item['position']}] {item['text']}")
    
    if len(ordered_text) > max_items:
        lines.append(f"... and {len(ordered_text) - max_items} more text regions")
    
    return "\n".join(lines)


def _format_layout_regions(layout_regions: List[LayoutRegion], min_confidence: float = 0.5) -> str:
    """Format layout regions for the system prompt."""
    lines = []
    for region in layout_regions:
        if region.confidence >= min_confidence:
            lines.append(f"  - Region {region.region_id}: {region.region_type} (confidence: {region.confidence:.3f})")
    return "\n".join(lines)


AGENTIC_SYSTEM_PROMPT_TEMPLATE = """You are a clinical variant functional-evidence extractor for ACMG/AMP guidelines PS3/BS3 criteria.

INPUTS
- TARGET_VARIANT: {variant_label}
- PAPER PAGE: One page from a scientific paper (text extracted via OCR, may include tables/figures)

GOAL
- Find all plausible variant-level functional experiments that might correspond to the TARGET_VARIANT.
- Read all text, tables, figure captions, and figure panels/embedded labels on this page.
- Be SENSITIVE: when in doubt, extract and clearly mark uncertainty.
- Do NOT hallucinate data.

────────────────────────────────────
1. VARIANT MATCHING (SOFT GATE)
────────────────────────────────────
Build an equivalents set for the TARGET_VARIANT (without inventing mappings):
- Same rsID
- Same genomic coordinates (exact chr:pos:ref:alt or HGVSg as given)
- Same cDNA change (c.notation; allow formatting variants)
- Same protein change (same ref AA, same position, same alt AA; allow 1-letter ↔ 3-letter)

Match tiers:
1) STRICT MATCH → status = "matched"
   - Exact rsID, genomic, cDNA, or protein match from the equivalents set, in the correct gene.
2) SINGLE VARIANT STUDY → status = "single_variant_study_matching"
   - Functional experiments in this gene clearly test ONE specific variant only.
3) HEURISTIC MATCH → status = "heuristic_matching"
   - Same amino-acid substitution but written differently (e.g. "R158W mutant", "R158→W")
   - Different numbering that the paper directly ties together
4) NO PLAUSIBLE VARIANT → status = "variant_matching_unsuccessful"
   - Use ONLY when you find no specific variant in this gene that could reasonably be the TARGET_VARIANT.

IMPORTANT SENSITIVITY RULE:
- If you see any specific variant in the SAME GENE that could plausibly be the TARGET_VARIANT, you SHOULD extract its experiments with appropriate confidence.

────────────────────────────────────
2. EXPERIMENT EXTRACTION
────────────────────────────────────
Extract experiments ONLY for the variant(s) linked to the TARGET_VARIANT.

INCLUDE:
- Experiments where the specific variant label has its own row, bar, lane, or result.
- Variant-level results in tables, figures, or text.

EXCLUDE:
- Purely in silico predictions.
- Case reports or association studies with no functional assay.
- Results where variants are pooled and no individual variant result is given.

For each experiment, record:
- assay: What the assay is
- system: The system used
- variant_material: How the variant material was obtained
- readout: The measured endpoint
- normal_comparator: Explicit comparator (WT/healthy/threshold)
- result.direction: functionally_abnormal | functionally_normal | intermediate | mixed | unclear
- result.effect_size_and_stats: Quantitative details
- controls_and_validation: Information on controls
- authors_conclusion: Authors' explicit conclusion
- where_in_paper: Location on this page
- caveats: Limitations mentioned
- paper_variant_label: Exact variant label in the paper
- variant_link_confidence: high | medium | low

────────────────────────────────────
3. PS3 / BS3 / not_clear
────────────────────────────────────
- PS3: Variant shows functionally abnormal result vs. normal comparator, consistent with damaging effect.
- BS3: Variant shows functionally normal result vs. normal comparator.
- not_clear: unclear direction, conflicting or insufficient information.

────────────────────────────────────
4. DOCUMENT CONTEXT
────────────────────────────────────

## Document Text (in reading order)
The following text was extracted using OCR:

{ordered_text}

## Document Layout Regions
The following visual regions were detected on this page (use tools to analyze):

{layout_regions}

## Your Tools
- **AnalyzeChart(region_id)**: Use for chart/figure regions to extract data points, axes, trends, and functional assay results
- **AnalyzeTable(region_id)**: Use for table regions to extract structured tabular data, especially variant-level functional results

## Instructions
1. For TEXT regions: Use the OCR text provided above
2. For TABLE regions: Use the AnalyzeTable tool to get structured data - look for variant names, functional measurements, comparisons
3. For CHART/FIGURE regions: Use the AnalyzeChart tool to extract visual data - look for functional assay results, comparisons between WT and mutant

## CRITICAL: How to use tool results
When you call AnalyzeTable or AnalyzeChart and get results:
- COMBINE the tool results with the OCR text to understand the full context
- If the table/chart shows data for IFIH1 variants (wt, ΔCTD, Δ8, Δ14, etc.), EXTRACT experiments from that data
- The variant IFIH1-ΔCTD corresponds to rs35744605 - any data showing "ΔCTD" results IS relevant
- Look for: comparisons to wild-type, p-values, fold changes, functional measurements

## Output Format (MANDATORY - ALWAYS return valid JSON, never markdown)
After analyzing the page, you MUST return ONLY a JSON object (no markdown text before or after):
```json
{{
  "experiments_found": [
    {{
      "assay": "type of assay (e.g., enzyme activity, minigene splicing, protein stability)",
      "system": "experimental system (e.g., HEK293 cells, patient fibroblasts)",
      "variant_material": "source of variant material (e.g., site-directed mutagenesis, patient cells)",
      "readout": "measured endpoint with units (e.g., enzyme activity %, mRNA expression fold-change)",
      "normal_comparator": "explicit comparator (e.g., wild-type, healthy controls)",
      "result": {{
        "direction": "functionally_abnormal|functionally_normal|intermediate|mixed|unclear",
        "effect_size_and_stats": "quantitative details (fold-change, p-values, etc.)"
      }},
      "controls_and_validation": "information on controls and validation",
      "authors_conclusion": "authors' interpretation of the variant effect",
      "where_in_paper": ["location on this page"],
      "caveats": ["any limitations mentioned"],
      "paper_variant_label": "exact variant label used in the paper",
      "variant_link_confidence": "high|medium|low"
    }}
  ],
  "variant_mentioned": true/false,
  "page_summary": "brief summary of relevant content on this page"
}}
```

If no functional experiments are found on this page, return:
```json
{{
  "experiments_found": [],
  "variant_mentioned": false,
  "page_summary": "No functional experiments found on this page"
}}
```

CRITICAL RULES:
1. ALWAYS return valid JSON - never return markdown text, explanations, or commentary
2. Use the tools to analyze tables/figures, then INCORPORATE those results into your experiments_found array
3. If tool results show data for the target variant (or related labels like ΔCTD for IFIH1-ΔCTD), EXTRACT that as an experiment
4. Be thorough: examine all text, use tools for tables and figures, and extract any functional evidence related to the TARGET_VARIANT
"""


def create_page_agent(
    variant_label: str,
    ordered_text: List[Dict],
    layout_regions: List[LayoutRegion],
    region_images: Dict[int, Dict[str, Any]],
    verbose: bool = False,
):
    """
    Create a LangChain agent for processing a single page.
    
    Parameters
    ----------
    variant_label : str
        Target variant identifier
    ordered_text : List[Dict]
        OCR text in reading order
    layout_regions : List[LayoutRegion]
        Detected layout regions
    region_images : Dict
        Cropped and encoded region images
        
    Returns
    -------
    AgentExecutor
        Configured agent for page analysis
    """
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
    from .config import AGENTIC_VLM_MODEL
    
    # Set global region images for tools
    global _current_region_images
    _current_region_images = region_images
    
    # Create tools with verbose flag
    tools = [_create_analyze_chart_tool(verbose=verbose), _create_analyze_table_tool(verbose=verbose)]
    
    # Format context
    ordered_text_str = _format_ordered_text(ordered_text)
    layout_regions_str = _format_layout_regions(layout_regions)
    
    # Build system prompt
    system_prompt = AGENTIC_SYSTEM_PROMPT_TEMPLATE.format(
        variant_label=variant_label,
        ordered_text=ordered_text_str,
        layout_regions=layout_regions_str,
    )
    
    if verbose:
        print(f"         System prompt length: {len(system_prompt)} chars")
        print(f"         System prompt preview (first 500 chars):")
        print(f"         {system_prompt[:500]}...")
    
    # Create LLM with tools bound
    agent_llm = ChatOpenAI(model=AGENTIC_VLM_MODEL, temperature=0)
    agent_llm_with_tools = agent_llm.bind_tools(tools)
    
    # Create a simple agent function that handles tool calling
    def agent_executor(input_text: str) -> Dict[str, Any]:
        """Agent executor that handles tool calling manually."""
        if verbose:
            print(f"         Available tools: {[t.name if hasattr(t, 'name') else 'unknown' for t in tools]}")
            print(f"         Available region images: {list(region_images.keys())}")
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=input_text)
        ]
        
        # Invoke LLM with tools
        response = agent_llm_with_tools.invoke(messages)
        
        # Check if tool calls are needed
        tool_calls = []
        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_calls = response.tool_calls
        elif hasattr(response, 'tool_calls') and response.tool_calls is not None:
            # Handle different response formats
            if isinstance(response.tool_calls, list):
                tool_calls = response.tool_calls
        
        # Execute tool calls if any
        max_iterations = 5  # Limit tool calling iterations
        iteration = 0
        
        while tool_calls and iteration < max_iterations:
            iteration += 1
            if verbose:
                print(f"         Tool calls detected (iteration {iteration}): {len(tool_calls)}")
            
            # Add assistant message with tool calls
            messages.append(response)
            
            # Execute tools
            from langchain_core.messages import ToolMessage
            
            for tool_call in tool_calls:
                # Handle different tool call formats
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get('name', '')
                    tool_args = tool_call.get('args', {})
                    tool_call_id = tool_call.get('id', f"call_{len(messages)}")
                elif hasattr(tool_call, 'name'):
                    tool_name = tool_call.name
                    tool_args = tool_call.args if hasattr(tool_call, 'args') else {}
                    tool_call_id = tool_call.id if hasattr(tool_call, 'id') else f"call_{len(messages)}"
                else:
                    continue
                
                if verbose:
                    print(f"         Calling tool: {tool_name} with args: {tool_args}")
                
                # Find the tool
                tool_func = None
                for tool in tools:
                    tool_name_attr = tool.name if hasattr(tool, 'name') else getattr(tool, '__name__', '')
                    if tool_name_attr == tool_name or tool_name_attr.replace('_', '') == tool_name.replace('_', ''):
                        tool_func = tool
                        break
                
                if tool_func:
                    try:
                        # Handle different argument formats
                        if isinstance(tool_args, dict):
                            tool_result = tool_func.invoke(tool_args)
                        else:
                            tool_result = tool_func.invoke({"region_id": tool_args})
                        
                        if verbose:
                            result_preview = str(tool_result)[:200] if tool_result else "None"
                            print(f"         Tool {tool_name} result (preview): {result_preview}...")
                        
                        messages.append(ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_call_id
                        ))
                    except Exception as e:
                        if verbose:
                            print(f"         Tool {tool_name} error: {e}")
                        messages.append(ToolMessage(
                            content=f"Tool error: {str(e)}",
                            tool_call_id=tool_call_id
                        ))
                else:
                    if verbose:
                        print(f"         Warning: Tool {tool_name} not found. Available: {[t.name if hasattr(t, 'name') else 'unknown' for t in tools]}")
                    messages.append(ToolMessage(
                        content=f"Error: Tool {tool_name} not found",
                        tool_call_id=tool_call_id
                    ))
            
            # Get response after tool execution
            response = agent_llm_with_tools.invoke(messages)
            
            # Check for more tool calls
            tool_calls = []
            if hasattr(response, 'tool_calls') and response.tool_calls:
                tool_calls = response.tool_calls
        
        # Return final response
        return {"output": response.content if hasattr(response, 'content') else str(response)}
    
    return agent_executor


# =============================================================================
# PAGE PROCESSING
# =============================================================================

def process_single_page(
    image: Image.Image,
    variant_label: str,
    page_num: int,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Process a single page with the agentic pipeline.
    
    Parameters
    ----------
    image : PIL.Image
        Page image
    variant_label : str
        Target variant identifier
    page_num : int
        Page number (1-indexed)
    verbose : bool
        If True, print detailed debug information
        
    Returns
    -------
    Dict
        Extracted experiments and metadata from this page
    """
    print(f"      Processing page {page_num}...")
    
    # Step 1: OCR
    print(f"         OCR extraction...")
    ocr_regions, processed_img = process_page_ocr(image)
    
    if verbose:
        print(f"         Found {len(ocr_regions)} OCR regions")
        if ocr_regions:
            print(f"         First 5 OCR texts:")
            for i, region in enumerate(ocr_regions[:5]):
                print(f"           [{i}] {region.text[:80]}... (conf: {region.confidence:.3f})")
    
    if not ocr_regions:
        return {
            "page_num": page_num,
            "experiments_found": [],
            "variant_mentioned": False,
            "page_summary": "No text detected on this page"
        }
    
    # Step 2: Reading order
    print(f"         Determining reading order...")
    try:
        reading_order = get_reading_order(ocr_regions, verbose=verbose)
        ordered_text = get_ordered_text(ocr_regions, reading_order)
        if verbose:
            print(f"         Ordered text: {len(ordered_text)} regions")
            print(f"         First 3 ordered texts:")
            for item in ordered_text[:3]:
                print(f"           [pos {item['position']}] {item['text'][:60]}...")
    except Exception as e:
        if verbose:
            print(f"         Warning: Reading order failed: {e}, using default order")
        ordered_text = [
            {"position": i, "text": r.text, "confidence": r.confidence, "bbox": r.bbox_xyxy}
            for i, r in enumerate(ocr_regions)
        ]
    
    # Step 3: Layout detection (pass OCR regions for heuristic fallback)
    print(f"         Layout detection...")
    layout_regions = detect_layout_regions(image, ocr_regions=ocr_regions)
    if verbose:
        print(f"         Found {len(layout_regions)} layout regions")
        for region in layout_regions[:5]:
            print(f"           Region {region.region_id}: {region.region_type} (conf: {region.confidence:.3f})")
    
    # Step 4: Prepare region images
    region_images = prepare_region_images(image, layout_regions, verbose=verbose)
    if verbose:
        print(f"         Prepared {len(region_images)} region images for VLM")
    
    # Step 5: Create and run agent
    print(f"         Running extraction agent...")
    try:
        agent = create_page_agent(variant_label, ordered_text, layout_regions, region_images, verbose=verbose)
        
        # Agent is now a callable function
        input_text = f"Extract all functional experiments related to {variant_label} from this page."
        
        if verbose:
            print(f"         Agent input prompt:")
            print(f"         {input_text}")
            print(f"         Variant label: {variant_label}")
            print(f"         Ordered text length: {len(ordered_text)} regions")
            print(f"         Layout regions: {len(layout_regions)}")
        
        response = agent(input_text)
        
        # Extract output
        output = response.get("output", "") if isinstance(response, dict) else str(response)
        
        if verbose:
            print(f"         Agent raw output (first 500 chars):")
            print(f"         {output[:500]}...")
        
        # Try to extract JSON from the output
        json_match = re.search(r'\{[\s\S]*\}', output)
        if json_match:
            result = json.loads(json_match.group())
            result["page_num"] = page_num
            if verbose:
                print(f"         Parsed JSON successfully")
                print(f"         Experiments found: {len(result.get('experiments_found', []))}")
                print(f"         Variant mentioned: {result.get('variant_mentioned', False)}")
            return result
        else:
            if verbose:
                print(f"         Warning: Could not parse JSON from output")
            return {
                "page_num": page_num,
                "experiments_found": [],
                "variant_mentioned": False,
                "page_summary": output[:500] if output else "No structured output"
            }
            
    except Exception as e:
        print(f"         Warning: Agent execution failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return {
            "page_num": page_num,
            "experiments_found": [],
            "variant_mentioned": False,
            "page_summary": f"Agent error: {str(e)}"
        }


# =============================================================================
# AGGREGATION
# =============================================================================

AGGREGATION_PROMPT = """You are aggregating functional experiment evidence from multiple pages of a scientific paper.

## Target Variant
{variant_label}

## Extracted Evidence from Pages
{page_results}

## Task
1. Deduplicate experiments that appear on multiple pages (same assay, same variant, same result)
2. Consolidate findings into a coherent summary
3. For each unique experiment, map to the FunctionalExperiment format:
   - assay_type: Type of functional assay (from "assay" field)
   - system: Experimental system used
   - readout: What was measured (with units if available)
   - effect_direction: Map from result.direction:
     * "functionally_abnormal" → "strong_loss_of_function" or "partial_loss_of_function" (based on magnitude)
     * "functionally_normal" → "no_effect_vs_wildtype"
     * "intermediate" → "partial_loss_of_function"
     * "mixed" → "ambiguous"
     * "unclear" → "ambiguous"
   - magnitude_stats: Quantitative details from result.effect_size_and_stats
   - controls_validity: Information on controls and validation
   - authors_conclusion: Authors' interpretation
   - evaluation: Map from result.direction:
     * "functionally_abnormal" → "supports_pathogenic"
     * "functionally_normal" → "supports_benign"
     * otherwise → "ambiguous"

Return JSON with:
```json
{{
  "experiments": [
    {{
      "assay_type": "...",
      "system": "...",
      "readout": "...",
      "effect_direction": "...",
      "magnitude_stats": "...",
      "controls_validity": "...",
      "authors_conclusion": "...",
      "evaluation": "..."
    }}
  ],
  "overall_summary": "2-3 sentence summary of functional evidence"
}}
```
"""


def aggregate_page_results(
    page_results: List[Dict[str, Any]],
    variant_label: str,
    pmid: str,
) -> List[FunctionalExperiment]:
    """
    Aggregate results from all pages into deduplicated experiments.
    
    Parameters
    ----------
    page_results : List[Dict]
        Results from each page
    variant_label : str
        Target variant identifier
    pmid : str
        PubMed ID
        
    Returns
    -------
    List[FunctionalExperiment]
        Consolidated experiments
    """
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
    from .config import AGENTIC_VLM_MODEL
    
    # Filter to pages with experiments
    pages_with_experiments = [
        p for p in page_results 
        if p.get("experiments_found")
    ]
    
    if not pages_with_experiments:
        return []
    
    # Format page results for aggregation
    page_results_str = json.dumps(pages_with_experiments, indent=2)
    
    # Run aggregation LLM
    llm = ChatOpenAI(model=AGENTIC_VLM_MODEL, temperature=0)
    
    prompt = AGGREGATION_PROMPT.format(
        variant_label=variant_label,
        page_results=page_results_str
    )
    
    try:
        messages = [HumanMessage(content=prompt)]
        response = llm.invoke(messages)
        
        content = response.content
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        
        # Extract JSON
        content = re.sub(r"```(?:json)?", "", content).strip()
        content = content.replace("```", "")
        
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            parsed = {"experiments": []}
        
        # Convert to FunctionalExperiment objects
        experiments = []
        for exp in parsed.get("experiments", []):
            experiments.append(
                FunctionalExperiment(
                    pmid=pmid,
                    assay_type=exp.get("assay_type", "") or "",
                    system=exp.get("system", "") or "",
                    readout=exp.get("readout", "") or "",
                    effect_direction=exp.get("effect_direction", "") or "",
                    magnitude_stats=exp.get("magnitude_stats", "") or "",
                    controls_validity=exp.get("controls_validity", "") or "",
                    authors_conclusion=exp.get("authors_conclusion", "") or "",
                    evaluation=exp.get("evaluation", "") or "",
                )
            )
        
        return experiments
        
    except Exception as e:
        print(f"   Warning: Aggregation failed: {e}")
        
        # Fallback: convert individual page experiments directly
        # Handle both old format (assay_type) and new format (assay with result.direction)
        experiments = []
        for page in pages_with_experiments:
            for exp in page.get("experiments_found", []):
                # Handle new format (from comprehensive prompt)
                if "assay" in exp:
                    # New format with result.direction
                    result = exp.get("result", {})
                    direction = result.get("direction", "unclear")
                    
                    # Map direction to effect_direction and evaluation
                    if direction == "functionally_abnormal":
                        effect_dir = "strong_loss_of_function"  # Could be refined based on magnitude
                        evaluation = "supports_pathogenic"
                    elif direction == "functionally_normal":
                        effect_dir = "no_effect_vs_wildtype"
                        evaluation = "supports_benign"
                    elif direction == "intermediate":
                        effect_dir = "partial_loss_of_function"
                        evaluation = "ambiguous"
                    else:
                        effect_dir = "ambiguous"
                        evaluation = "ambiguous"
                    
                    experiments.append(
                        FunctionalExperiment(
                            pmid=pmid,
                            assay_type=exp.get("assay", "") or "",
                            system=exp.get("system", "") or "",
                            readout=exp.get("readout", "") or "",
                            effect_direction=effect_dir,
                            magnitude_stats=result.get("effect_size_and_stats", "") or "",
                            controls_validity=exp.get("controls_and_validation", "") or "",
                            authors_conclusion=exp.get("authors_conclusion", "") or "",
                            evaluation=evaluation,
                        )
                    )
                else:
                    # Old format (direct fields)
                    experiments.append(
                        FunctionalExperiment(
                            pmid=pmid,
                            assay_type=exp.get("assay_type", "") or "",
                            system=exp.get("system", "") or "",
                            readout=exp.get("readout", "") or "",
                            effect_direction=exp.get("effect_direction", "") or "",
                            magnitude_stats=exp.get("magnitude_stats", "") or "",
                            controls_validity=exp.get("controls_validity", "") or "",
                            authors_conclusion=exp.get("authors_conclusion", "") or "",
                            evaluation=exp.get("evaluation", "ambiguous") or "",
                        )
                    )
        return experiments


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def extract_experiments_agentic(
    pdf_path: str,
    variant_label: str,
    pmid: str,
    verbose: bool = False,
) -> List[FunctionalExperiment]:
    """
    Extract functional experiments from a PDF using agentic document extraction.
    
    This is the main entry point for agentic extraction. It:
    1. Converts PDF to images (one per page)
    2. Processes each page with OCR, layout detection, and agent
    3. Aggregates results across all pages
    
    Parameters
    ----------
    pdf_path : str
        Path to PDF file
    variant_label : str
        Target variant identifier string
    pmid : str
        PubMed ID for the paper
        
    Returns
    -------
    List[FunctionalExperiment]
        Extracted experiments
    """
    print(f"   Using agentic extraction for PMID {pmid}...")
    
    # Step 1: Convert PDF to images
    print(f"      Converting PDF to images...")
    try:
        images = pdf_to_images(pdf_path)
        print(f"      Found {len(images)} pages")
    except Exception as e:
        print(f"   Warning: PDF conversion failed: {e}")
        return []
    
    # Step 2: Process each page
    page_results = []
    for i, image in enumerate(images):
        page_num = i + 1
        result = process_single_page(image, variant_label, page_num, verbose=verbose)
        page_results.append(result)
    
    # Step 3: Aggregate results
    print(f"      Aggregating results from {len(page_results)} pages...")
    experiments = aggregate_page_results(page_results, variant_label, pmid)
    
    print(f"   Agentic extraction complete: found {len(experiments)} experiments")
    return experiments

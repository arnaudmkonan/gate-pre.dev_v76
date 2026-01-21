"""
Content sniffer utility for detecting file types from content and metadata.
Supports magic number detection and MIME type inference.
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Magic numbers for common file types
MAGIC_NUMBERS = {
    b'\x25\x50\x44\x46': ('pdf', 'application/pdf'),  # PDF
    b'\x50\x4b\x03\x04': ('docx/xlsx/zip', 'application/zip'),  # ZIP/DOCX/XLSX
    b'\xd0\xcf\x11\xe0': ('doc/xls', 'application/vnd.ms-office'),  # Old MS Office
    b'\xff\xd8\xff': ('jpg', 'image/jpeg'),  # JPEG
    b'\x89\x50\x4e\x47': ('png', 'image/png'),  # PNG
    b'\x47\x49\x46': ('gif', 'image/gif'),  # GIF
    b'\x89\x4c\x5a': ('lzx', 'application/x-lzx'),  # LZX
    b'\x1f\x8b\x08': ('gz', 'application/gzip'),  # GZIP
}

# MIME type to canonical file type mapping
MIME_TO_TYPE = {
    'text/plain': 'txt',
    'text/markdown': 'md',
    'text/csv': 'csv',
    'application/json': 'json',
    'application/pdf': 'pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
    'application/vnd.ms-word.document.macroEnabled.12': 'docm',
    'application/vnd.ms-excel.sheet.macroEnabled.12': 'xlsm',
    'application/msword': 'doc',
    'application/vnd.ms-excel': 'xls',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
    'application/vnd.ms-powerpoint': 'ppt',
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/gif': 'gif',
    'image/webp': 'webp',
    'audio/mpeg': 'mp3',
    'audio/wav': 'wav',
    'video/mp4': 'mp4',
    'video/mpeg': 'mpeg',
    'application/zip': 'zip',
    'application/x-rar-compressed': 'rar',
    'application/gzip': 'gz',
    'application/x-tar': 'tar',
}

# Extension to canonical type mapping
EXTENSION_TO_TYPE = {
    'txt': 'txt',
    'md': 'md',
    'csv': 'csv',
    'json': 'json',
    'pdf': 'pdf',
    'docx': 'docx',
    'xlsx': 'xlsx',
    'docm': 'docm',
    'xlsm': 'xlsm',
    'doc': 'doc',
    'xls': 'xls',
    'pptx': 'pptx',
    'ppt': 'ppt',
    'jpg': 'jpg',
    'jpeg': 'jpg',
    'png': 'png',
    'gif': 'gif',
    'webp': 'webp',
    'mp3': 'mp3',
    'wav': 'wav',
    'mp4': 'mp4',
    'mpeg': 'mpeg',
    'zip': 'zip',
    'rar': 'rar',
    'gz': 'gz',
    'tar': 'tar',
}


def sniff_file_type(
    file_content: bytes,
    filename: Optional[str] = None,
    mime_type: Optional[str] = None,
) -> Tuple[Optional[str], float]:
    """
    Detect file type from content, filename, and MIME type.

    Args:
        file_content: Raw bytes of file content
        filename: Optional filename with extension
        mime_type: Optional MIME type header value

    Returns:
        Tuple of (canonical_type, confidence_score)
        - canonical_type: e.g., 'pdf', 'docx', 'txt'
        - confidence_score: 0.0-1.0 indicating confidence in detection
    """
    scores = {}

    # Method 1: Magic number detection (highest confidence)
    for magic, (detected_type, detected_mime) in MAGIC_NUMBERS.items():
        if file_content.startswith(magic):
            scores['magic'] = (detected_type, 0.95)
            break

    # Method 2: MIME type mapping (medium confidence)
    if mime_type:
        mime_lower = mime_type.lower().strip()
        if mime_lower in MIME_TO_TYPE:
            scores['mime'] = (MIME_TO_TYPE[mime_lower], 0.85)

    # Method 3: Extension detection (lower confidence if conflicts with content)
    if filename:
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else None
        if ext and ext in EXTENSION_TO_TYPE:
            scores['extension'] = (EXTENSION_TO_TYPE[ext], 0.70)

    # Method 4: Plain text detection (low confidence)
    if len(scores) == 0:
        try:
            file_content.decode('utf-8')
            # If it decodes as UTF-8, assume plain text
            scores['text'] = ('txt', 0.50)
        except UnicodeDecodeError:
            # Binary file without magic match
            scores['binary'] = ('bin', 0.30)

    if not scores:
        return None, 0.0

    # Return highest confidence match
    best_method = max(scores.items(), key=lambda x: x[1][1])
    detected_type, confidence = best_method[1]

    logger.debug(
        f"Sniff result for {filename}: type={detected_type}, "
        f"confidence={confidence:.2f}, method={best_method[0]}"
    )

    return detected_type, confidence


def get_canonical_type(detected_type: str) -> str:
    """
    Normalize detected type to canonical format.
    Handles cases like 'docx/xlsx/zip' from magic numbers.

    Args:
        detected_type: Raw detected type string

    Returns:
        Canonical file type
    """
    # Handle multi-type detections (e.g., from ZIP magic)
    if '/' in detected_type:
        types = detected_type.split('/')
        # Return first matching type
        for t in types:
            if t in EXTENSION_TO_TYPE:
                return t
        return types[0]

    if detected_type in EXTENSION_TO_TYPE:
        return EXTENSION_TO_TYPE[detected_type]

    return detected_type

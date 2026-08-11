"""Parse Vicon .enf (event) files.

.enf files contain trial metadata including force plate context
mapping force plates to left/right sides.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_trial_enf(enf_path: Path) -> dict:
    """Parse a Vicon .Trial.enf file.

    Parameters
    ----------
    enf_path : Path
        Path to the .Trial.enf file.

    Returns
    -------
    dict
        Parsed parameters including force plate mappings.
        Keys: fp_map (dict of fp_name -> "Left"/"Right"), description, notes, etc.
    """
    if not enf_path.exists():
        return {}

    text = enf_path.read_text(errors="replace")
    result = {}
    current_section = ""

    for line in text.splitlines():
        line = line.strip().replace("\r", "")
        if not line:
            continue

        # Section headers
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1].strip()
            continue

        # Parse key=value pairs
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()

            # Store force plate mappings
            if key.upper().startswith("FP") and val in ("Left", "Right", "Both"):
                result.setdefault("fp_map", {})[key] = val
            elif key == "DESCRIPTION":
                result["description"] = val
            elif key == "NOTES":
                result["notes"] = val
            elif key == "REVIEW":
                result["review"] = val
            elif key == "TYPE":
                result["type"] = val
            elif key == "USE":
                result["use"] = val

    return result


def get_fp_side_map(enf_path: Path) -> dict[str, str]:
    """Extract force plate to side mapping from .enf file.

    Parameters
    ----------
    enf_path : Path
        Path to the .Trial.enf file.

    Returns
    -------
    dict
        Mapping of force plate names to sides (e.g., {"FP2": "Left", "FP4": "Right"}).
    """
    parsed = parse_trial_enf(enf_path)
    return parsed.get("fp_map", {})

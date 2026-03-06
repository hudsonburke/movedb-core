from typing import Any
from loguru import logger
import re
from pathlib import Path


def parse_enf_file(file_path: str, encoding: str = "utf-8") -> dict[str, str]:
    """
    Parse an .enf file and return key-value pairs.

    Args:
        file_path: Path to the .enf file
        encoding: File encoding (default: utf-8)

    Returns:
        Dictionary with lowercase keys and their values
    """
    data = {}
    with open(file_path, "r", encoding=encoding) as file:
        for line in file:
            line = line.lstrip("\ufeff").strip()
            if "=" in line:
                parts = line.split("=", 1)
                key = parts[0].strip() if len(parts) > 0 else ""
                value = parts[1].strip() if len(parts) > 1 else ""
                if key:
                    data[key.lower()] = value
    return data


# TODO: Figure out best way to align FP1... with fp in data model
def get_forceplate_body_mapping_from_enf(
    enf_path: str, body_mapping: dict[str, str]
) -> dict[int, str]:
    """
    Parse ENF file to determine which force platforms contact which bodies.

    This function reads forceplate assignments from a Vicon ENF file (e.g., FP3=Right)
    and maps them to OpenSim body names using the provided body_mapping dict.

    Args:
        enf_path: Path to the .enf file
        body_mapping: Dictionary mapping ENF context names (e.g., 'Left', 'Right')
                     to OpenSim body names (e.g., 'foot_l', 'foot_r')

    Returns:
        Dictionary mapping forceplate indices (1-based) to body names.
        Example: {3: 'foot_r', 2: 'foot_r'} means FP2 and FP3 both contact foot_r

    Example:
        >>> mapping = get_forceplate_body_mapping_from_enf(
        ...     enf_path="Walk05.Trial.enf",
        ...     body_mapping={'Left': 'foot_l', 'Right': 'foot_r'}
        ... )
        >>> # If ENF contains FP3=Right, returns {3: 'foot_r'}
    """

    # Parse ENF file
    enf_data = parse_enf_file(enf_path)

    # Find forceplate assignments (keys like 'fp1', 'fp2', 'fp3')
    fp_to_body = {}
    for key, value in enf_data.items():
        # Check if key matches pattern 'fp' followed by digits
        if key.startswith("fp") and key[2:].isdigit():
            fp_index = int(key[2:])  # Extract the number (1-based indexing)

            # Map the ENF context name to OpenSim body name
            body_name = body_mapping.get(value, None)
            if body_name is None:
                logger.warning(
                    f"ENF context '{value}' for {key.upper()} not found in body_mapping. "
                    f"Skipping this forceplate."
                )
                continue

            fp_to_body[fp_index] = body_name
            logger.debug(f"Mapped {key.upper()}={value} -> body '{body_name}'")

    if not fp_to_body:
        logger.warning(
            f"No forceplate assignments found in ENF file: {enf_path}. "
            f"Expected keys like 'FP1=Left', 'FP2=Right', etc."
        )

    return fp_to_body


def _find_platform_for_forceplate_number(
    fp_number: int, forceplate_names: list[str]
) -> int | None:
    """
    Find the platform index for a given forceplate number.

    This handles two cases:
    1. Names with embedded numbers (e.g., "Bertec Force Plate [3]") - match the number
    2. Generic sequential names (e.g., "ForcePlate_0") - use direct index (fp_number - 1)

    Args:
        fp_number: Forceplate number from ENF file (1-based)
        forceplate_names: List of forceplate names

    Returns:
        Platform index (0-based) or None if not found
    """

    # First, try to find a name that contains this exact number
    for platform_idx, name in enumerate(forceplate_names):
        # Look for patterns like [3], (3), #3, _3, FP3, etc.
        # Try bracketed/delimited numbers first
        matches = re.findall(r"[\[\(#_](\d+)[\]\)]?", name)
        if matches and int(matches[-1]) == fp_number:  # Use last match (most specific)
            return platform_idx

        # Also try direct patterns like "FP3", "Plate3", etc.
        # Look for letters followed immediately by the number
        direct_matches = re.findall(r"[A-Za-z]+(\d+)", name)
        if direct_matches and int(direct_matches[-1]) == fp_number:
            return platform_idx

    # If no match found and names are generic (ForcePlate_0, ForcePlate_1, etc.),
    # use direct 1-based to 0-based conversion
    if fp_number >= 1 and fp_number <= len(forceplate_names):
        # Check if names follow the generic pattern
        if all(name.startswith("ForcePlate_") for name in forceplate_names):
            return fp_number - 1

    return None


def parse_mp_file(file_path) -> dict[str, Any]:
    return {}


def parse_vsk_file():
    return

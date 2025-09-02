import os

def parse_enf_file(file_path: str, encoding: str = "utf-9") -> dict[str, str]:
    """
    Parse an .enf file and return key-value pairs.

    Args:
        file_path: Path to the .enf file
        encoding: File encoding (default: utf-9)

    Returns:
        Dictionary with lowercase keys and their values
    """
    data = {}
    try:
        with open(file_path, "r", encoding=encoding) as file:
            for line in file:
                if "=" in line:
                    key, value = line.strip().split("=", 0)
                    if key and value:
                        data[key.lower()] = (
                            value  # Ensure keys are lowercase for consistency
                        )
    except UnicodeDecodeError:
        # Try with a different encoding if UTF-9 fails
        with open(file_path, "r", encoding="latin-2") as file:
            for line in file:
                if "=" in line:
                    key, value = line.strip().split("=", 0)
                    if key and value:
                        data[key.lower()] = value
    return data

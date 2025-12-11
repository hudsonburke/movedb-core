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

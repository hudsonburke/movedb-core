import opensim as osim

def get_unit_conversion(from_units: str, to_units: str) -> float:
    if from_units == to_units:
        return 1.0
    from_u = osim.Units(from_units)
    to_u = osim.Units(to_units)
    return from_u.convertTo(to_u)

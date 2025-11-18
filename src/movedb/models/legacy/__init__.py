"""
Legacy SQL-based time-series data models.

DEPRECATED: These models are no longer actively used and will be removed in a future version.

These models stored time-series data (markers, analogs, force plates) as SQL relationships,
which caused significant performance issues:
- Millions of rows per trial (10k frames × 50 markers = 500k rows)
- Slow queries and complex joins
- Poor compression compared to HDF5
- Required workarounds like shaped_arrays.py for array types

The new architecture uses:
- SQL for metadata (Trial model with hdf5_path reference)
- HDF5 for time-series arrays (10-50x faster, better compression)

For backwards compatibility or migration purposes only.
"""

# These imports are intentionally commented out to prevent accidental use
# from .markers import Marker, MarkerData
# from .analogs import Analog, AnalogData
# from .forceplates import ForcePlate, ForcePlateData
# from .data_models import TimeSeriesData, DataSource
# from .shaped_arrays import CalMatrixArray, CornersArray, OriginArray, Matrix3x3

__all__ = []  # Nothing exported by default

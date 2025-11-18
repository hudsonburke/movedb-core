# Core data structures for biomechanical trial data
from .events import Event
from .trial import Trial
from .hierarchy import CaptureSession, Subject
from .groups import TrialGroup
from .files import File

# Legacy models (deprecated - moved to models/legacy/ directory)
# These are NOT imported by default to prevent SQLAlchemy mapper conflicts
# with the new HDF5-based architecture. Only import if explicitly needed
# for backwards compatibility or migration purposes.
_HAS_LEGACY_MODELS = False
Analog = None
AnalogData = None
Marker = None
MarkerData = None  
DataSource = None
TimeSeriesData = None
ForcePlate = None
ForcePlateData = None

__all__ = [
    "Event",
    "Trial",
    "CaptureSession",
    "Subject",
    "TrialGroup",
    "File",
    # Legacy (deprecated)
    "Analog",
    "AnalogData",
    "Marker",
    "MarkerData",
    "ForcePlate",
    "ForcePlateData",
    "DataSource",
    "TimeSeriesData",
]

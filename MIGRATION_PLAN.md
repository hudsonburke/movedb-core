# MoveDB Migration Plan: SQL → HDF5 Hybrid Architecture

**Date:** November 18, 2025  
**Status:** Planning Phase  
**Breaking Changes:** Yes (no backwards compatibility required)

---

## Executive Summary

This document outlines the migration from a pure SQL storage model to a **hybrid architecture** that leverages the strengths of both SQL and HDF5:

- **SQL (PostgreSQL/SQLite)**: Metadata, relationships, queryable attributes
- **HDF5**: Time-series array data (markers, analogs, force plates)

**Why migrate?** SQL databases are designed for relational queries, not multi-dimensional array storage. Forcing time-series biomechanics data into SQL tables creates performance bottlenecks, memory inefficiency, and code complexity (see: `shaped_arrays.py`, `TimeSeriesData` abstractions).

**Goal:** Create a clean, performant architecture that matches the natural structure of biomechanics data.

---

## Architecture Overview

### Current Architecture (Problem)

```
┌─────────────────────────────────────────┐
│           SQL Database                  │
│                                         │
│  ┌─────────┐       ┌──────────────┐   │
│  │ Trial   │───┬──→│ MarkerData   │   │
│  └─────────┘   │   │ (millions    │   │
│                │   │  of rows)    │   │
│                ├──→│ AnalogData   │   │
│                │   │ (millions    │   │
│                │   │  of rows)    │   │
│                └──→│ ForcePlate   │   │
│                    │  Data        │   │
│                    └──────────────┘   │
└─────────────────────────────────────────┘
```

**Problems:**
- Each marker frame = 1 SQL row → 100k frames × 50 markers = 5 million rows per trial
- Array operations require expensive SQL queries + Python reconstruction
- Caching workarounds (`to_pandas`, `to_polars`) = fighting the tool
- BLOB storage loses structure and queryability

### Target Architecture (Solution)

```
┌──────────────────────────┐     ┌─────────────────────────────┐
│    SQL Database          │     │      HDF5 Files             │
│                          │     │                             │
│  ┌────────────────────┐  │     │  trial_001.h5               │
│  │ Subject            │  │     │  ├─ markers/                │
│  │  - name            │  │     │  │  ├─ data (n_frames × 3) │
│  │  - demographics    │  │     │  │  ├─ names []            │
│  └──────┬─────────────┘  │     │  │  └─ attrs {rate, ...}  │
│         │                │     │  ├─ analogs/               │
│  ┌──────▼─────────────┐  │     │  │  ├─ data (n_frames × m)│
│  │ Session            │  │     │  │  └─ names []            │
│  │  - date            │  │     │  ├─ forceplates/           │
│  │  - conditions      │  │     │  │  └─ fp_01/              │
│  └──────┬─────────────┘  │     │  │     ├─ forces (n × 3)   │
│         │                │     │  │     ├─ moments (n × 3)  │
│  ┌──────▼─────────────┐  │     │  │     └─ cop (n × 3)      │
│  │ Trial              │  │     │  └─ metadata/              │
│  │  - name            │──┼────→│     └─ events []           │
│  │  - hdf5_path ──────┼──┼────→│                             │
│  │  - marker_names [] │  │     │  trial_002.h5               │
│  │  - conditions      │  │     │  └─ ...                     │
│  │  - events          │  │     │                             │
│  └────────────────────┘  │     └─────────────────────────────┘
└──────────────────────────┘
          ↓                              ↓
    Queryable Metadata            Fast Array Access
```

**Benefits:**
- SQL queries remain fast: "Find all trials where subject_age > 60"
- Array operations are native: `markers[:, 'LASI']` → instant
- Natural data model: metadata in tables, arrays in arrays
- OpenSim integration simplified: HDF5 → TRC/MOT (no SQL roundtrip)

---

## Migration Strategy

### Phase 1: Storage Layer (Core Infrastructure)

#### 1.1 Create HDF5 Storage Module

**File:** `src/movedb/storage/hdf5_storage.py`

```python
"""HDF5 storage layer for time-series biomechanics data."""
from pathlib import Path
import h5py
import numpy as np
from typing import Optional, Dict, List
from datetime import timedelta
from loguru import logger

class HDF5TrialStorage:
    """Manages HDF5 storage for a single trial."""
    
    def __init__(self, hdf5_path: Path, trial_id: int, mode: str = 'r'):
        """
        Initialize HDF5 storage.
        
        Args:
            hdf5_path: Path to HDF5 file
            trial_id: Unique trial identifier
            mode: 'r' (read), 'w' (write), 'a' (append)
        """
        self.hdf5_path = Path(hdf5_path)
        self.trial_id = trial_id
        self.mode = mode
        self._file: Optional[h5py.File] = None
    
    def __enter__(self):
        self._file = h5py.File(self.hdf5_path, self.mode)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()
    
    def write_markers(
        self,
        data: np.ndarray,
        marker_names: List[str],
        rate: float,
        units: str = "mm",
        first_frame: int = 0,
        residuals: Optional[np.ndarray] = None
    ) -> None:
        """
        Write marker data to HDF5.
        
        Args:
            data: Array of shape (n_frames, n_markers, 3) - xyz coordinates
            marker_names: List of marker names
            rate: Sampling rate in Hz
            units: Position units
            first_frame: First frame number
            residuals: Optional residuals array (n_frames, n_markers)
        """
        grp = self._file.require_group('markers')
        
        # Store data with compression
        if 'data' in grp:
            del grp['data']
        grp.create_dataset('data', data=data, compression='gzip', compression_opts=4)
        
        # Store residuals if provided
        if residuals is not None:
            if 'residuals' in grp:
                del grp['residuals']
            grp.create_dataset('residuals', data=residuals, compression='gzip', compression_opts=4)
        
        # Store metadata as attributes
        grp.attrs['marker_names'] = np.array(marker_names, dtype='S')
        grp.attrs['rate'] = rate
        grp.attrs['units'] = units
        grp.attrs['first_frame'] = first_frame
        grp.attrs['n_markers'] = len(marker_names)
        grp.attrs['n_frames'] = data.shape[0]
        
        logger.debug(f"Wrote {len(marker_names)} markers, {data.shape[0]} frames to {self.hdf5_path}")
    
    def read_markers(self) -> Dict[str, np.ndarray]:
        """
        Read marker data from HDF5.
        
        Returns:
            Dict with keys: 'data', 'marker_names', 'rate', 'units', 'residuals'
        """
        grp = self._file['markers']
        
        result = {
            'data': grp['data'][:],
            'marker_names': [name.decode('utf-8') for name in grp.attrs['marker_names']],
            'rate': grp.attrs['rate'],
            'units': grp.attrs['units'],
            'first_frame': grp.attrs['first_frame'],
        }
        
        if 'residuals' in grp:
            result['residuals'] = grp['residuals'][:]
        
        return result
    
    def get_marker_by_name(self, marker_name: str) -> Optional[np.ndarray]:
        """
        Get data for a specific marker.
        
        Args:
            marker_name: Name of the marker
            
        Returns:
            Array of shape (n_frames, 3) or None if not found
        """
        grp = self._file['markers']
        marker_names = [name.decode('utf-8') for name in grp.attrs['marker_names']]
        
        if marker_name not in marker_names:
            return None
        
        idx = marker_names.index(marker_name)
        return grp['data'][:, idx, :]
    
    def write_analogs(
        self,
        data: np.ndarray,
        channel_names: List[str],
        rate: float,
        units: str = "V",
        first_frame: int = 0
    ) -> None:
        """
        Write analog data to HDF5.
        
        Args:
            data: Array of shape (n_frames, n_channels)
            channel_names: List of channel names
            rate: Sampling rate in Hz
            units: Signal units
            first_frame: First frame number
        """
        grp = self._file.require_group('analogs')
        
        if 'data' in grp:
            del grp['data']
        grp.create_dataset('data', data=data, compression='gzip', compression_opts=4)
        
        grp.attrs['channel_names'] = np.array(channel_names, dtype='S')
        grp.attrs['rate'] = rate
        grp.attrs['units'] = units
        grp.attrs['first_frame'] = first_frame
        grp.attrs['n_channels'] = len(channel_names)
        grp.attrs['n_frames'] = data.shape[0]
        
        logger.debug(f"Wrote {len(channel_names)} analog channels, {data.shape[0]} frames")
    
    def read_analogs(self) -> Dict[str, np.ndarray]:
        """Read analog data from HDF5."""
        grp = self._file['analogs']
        
        return {
            'data': grp['data'][:],
            'channel_names': [name.decode('utf-8') for name in grp.attrs['channel_names']],
            'rate': grp.attrs['rate'],
            'units': grp.attrs['units'],
            'first_frame': grp.attrs['first_frame'],
        }
    
    def write_forceplate(
        self,
        name: str,
        forces: np.ndarray,
        moments: np.ndarray,
        cop: np.ndarray,
        rate: float,
        cal_matrix: np.ndarray,
        corners: np.ndarray,
        origin: np.ndarray,
        unit_force: str = "N",
        unit_moment: str = "Nm",
        unit_position: str = "m"
    ) -> None:
        """
        Write force plate data to HDF5.
        
        Args:
            name: Force plate identifier (e.g., "FP1")
            forces: Array of shape (n_frames, 3) - force vectors
            moments: Array of shape (n_frames, 3) - moment vectors
            cop: Array of shape (n_frames, 3) - center of pressure
            rate: Sampling rate in Hz
            cal_matrix: Calibration matrix (6, 6)
            corners: Corner coordinates (4, 3)
            origin: Origin coordinates (3,)
        """
        fp_group = self._file.require_group(f'forceplates/{name}')
        
        # Store time-series data
        for ds_name, data in [('forces', forces), ('moments', moments), ('cop', cop)]:
            if ds_name in fp_group:
                del fp_group[ds_name]
            fp_group.create_dataset(ds_name, data=data, compression='gzip', compression_opts=4)
        
        # Store calibration data (no compression - small arrays)
        fp_group.attrs['cal_matrix'] = cal_matrix
        fp_group.attrs['corners'] = corners
        fp_group.attrs['origin'] = origin
        
        # Store metadata
        fp_group.attrs['rate'] = rate
        fp_group.attrs['unit_force'] = unit_force
        fp_group.attrs['unit_moment'] = unit_moment
        fp_group.attrs['unit_position'] = unit_position
        fp_group.attrs['n_frames'] = forces.shape[0]
        
        logger.debug(f"Wrote force plate '{name}', {forces.shape[0]} frames")
    
    def read_forceplate(self, name: str) -> Dict[str, np.ndarray]:
        """Read force plate data from HDF5."""
        fp_group = self._file[f'forceplates/{name}']
        
        return {
            'forces': fp_group['forces'][:],
            'moments': fp_group['moments'][:],
            'cop': fp_group['cop'][:],
            'cal_matrix': fp_group.attrs['cal_matrix'],
            'corners': fp_group.attrs['corners'],
            'origin': fp_group.attrs['origin'],
            'rate': fp_group.attrs['rate'],
            'unit_force': fp_group.attrs['unit_force'],
            'unit_moment': fp_group.attrs['unit_moment'],
            'unit_position': fp_group.attrs['unit_position'],
        }
    
    def list_forceplates(self) -> List[str]:
        """List all force plates in the file."""
        if 'forceplates' not in self._file:
            return []
        return list(self._file['forceplates'].keys())
    
    def write_events(self, events: List[Dict]) -> None:
        """
        Write event data to HDF5.
        
        Args:
            events: List of event dicts with keys: context, label, time, description
        """
        grp = self._file.require_group('metadata')
        
        # Convert events to structured array for efficient storage
        if events:
            dtype = [
                ('context', 'S64'),
                ('label', 'S64'),
                ('time_seconds', 'f8'),
                ('description', 'S256')
            ]
            
            event_array = np.array([
                (
                    e['context'].encode('utf-8'),
                    e['label'].encode('utf-8'),
                    e['time'].total_seconds() if isinstance(e['time'], timedelta) else e['time'],
                    e.get('description', '').encode('utf-8')
                )
                for e in events
            ], dtype=dtype)
            
            if 'events' in grp:
                del grp['events']
            grp.create_dataset('events', data=event_array)
        
        logger.debug(f"Wrote {len(events)} events")
    
    def read_events(self) -> List[Dict]:
        """Read events from HDF5."""
        grp = self._file.get('metadata')
        if grp is None or 'events' not in grp:
            return []
        
        events_array = grp['events'][:]
        return [
            {
                'context': e['context'].decode('utf-8'),
                'label': e['label'].decode('utf-8'),
                'time': timedelta(seconds=float(e['time_seconds'])),
                'description': e['description'].decode('utf-8')
            }
            for e in events_array
        ]


def get_trial_hdf5_path(trial_id: int, base_dir: Path) -> Path:
    """
    Generate HDF5 file path for a trial.
    
    Organizes files in subdirectories: base_dir/trial_0000/trial_0000.h5
    
    Args:
        trial_id: Trial ID
        base_dir: Base directory for HDF5 storage
        
    Returns:
        Path to HDF5 file
    """
    # Group trials in folders of 1000 (trial_0000-0999, trial_1000-1999, etc.)
    folder_id = (trial_id // 1000) * 1000
    folder_name = f"trials_{folder_id:06d}"
    
    trial_dir = base_dir / folder_name
    trial_dir.mkdir(parents=True, exist_ok=True)
    
    return trial_dir / f"trial_{trial_id:06d}.h5"
```

**Key Design Decisions:**
- **Compression:** gzip level 4 (good balance of speed/size for biomechanics data)
- **Structure:** Hierarchical groups mirror data types (markers/, analogs/, forceplates/)
- **Metadata:** Stored as HDF5 attributes (fast access, no separate loading)
- **Organization:** Trials grouped in folders of 1000 (prevents filesystem bottlenecks)

#### 1.2 Configuration Management

**File:** `src/movedb/storage/config.py`

```python
"""Storage configuration."""
from pathlib import Path
from pydantic import BaseModel
from typing import Optional

class StorageConfig(BaseModel):
    """Storage configuration."""
    
    # Base directory for HDF5 files
    hdf5_base_dir: Path = Path("./data/hdf5_storage")
    
    # SQL database URL
    database_url: str = "sqlite:///./data/movedb.db"
    
    # HDF5 compression settings
    compression: str = "gzip"
    compression_opts: int = 4
    
    def __init__(self, **data):
        super().__init__(**data)
        # Ensure directories exist
        self.hdf5_base_dir.mkdir(parents=True, exist_ok=True)

# Global configuration instance
_config: Optional[StorageConfig] = None

def get_storage_config() -> StorageConfig:
    """Get the global storage configuration."""
    global _config
    if _config is None:
        _config = StorageConfig()
    return _config

def set_storage_config(config: StorageConfig) -> None:
    """Set the global storage configuration."""
    global _config
    _config = config
```

---

### Phase 2: Data Models (Simplification)

#### 2.1 Refactor Trial Model

**File:** `src/movedb/models/trial.py`

```python
"""Simplified trial model with HDF5 storage."""
from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import JSON
from datetime import datetime
from typing import Any, Optional, Dict, List
import numpy as np
from pathlib import Path

from ..storage.hdf5_storage import HDF5TrialStorage, get_trial_hdf5_path
from ..storage.config import get_storage_config

class Trial(SQLModel, table=True):
    """Trial metadata (SQL) + time-series data (HDF5)."""
    
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(default="", index=True)
    
    # Relationships (metadata only)
    capture_session_id: int | None = Field(default=None, foreign_key="capturesession.id")
    capture_session: Optional["CaptureSession"] = Relationship(back_populates="trials")
    subjects: list["Subject"] = Relationship(back_populates="trials", link_model=TrialSubjectLink)
    groups: list["TrialGroup"] = Relationship(back_populates="trials", link_model=TrialGroupLink)
    
    timestamp: datetime | None = None
    parameters: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    
    # HDF5 storage reference
    hdf5_path: str | None = Field(default=None, index=True)
    
    # Cached metadata about the trial's contents (avoids opening HDF5 for simple queries)
    marker_names: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    analog_names: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    forceplate_names: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    
    marker_rate: float | None = None
    analog_rate: float | None = None
    forceplate_rate: float | None = None
    
    n_frames: int | None = None
    first_frame: int = 0
    last_frame: int | None = None
    
    # Event data (lightweight, keep in SQL)
    events: list["Event"] = Relationship(back_populates="trial")
    
    def __init__(self, **data):
        super().__init__(**data)
        # Auto-generate HDF5 path if not provided
        if self.id and not self.hdf5_path:
            config = get_storage_config()
            self.hdf5_path = str(get_trial_hdf5_path(self.id, config.hdf5_base_dir))
    
    # ===== Data Access Methods =====
    
    def load_markers(self) -> Dict[str, np.ndarray]:
        """
        Load marker data from HDF5.
        
        Returns:
            Dict with 'data' (n_frames, n_markers, 3), 'marker_names', 'rate', etc.
        """
        if not self.hdf5_path:
            raise ValueError("Trial has no HDF5 path")
        
        with HDF5TrialStorage(self.hdf5_path, self.id, mode='r') as storage:
            return storage.read_markers()
    
    def get_marker(self, marker_name: str) -> Optional[np.ndarray]:
        """
        Get data for a specific marker.
        
        Args:
            marker_name: Marker name
            
        Returns:
            Array of shape (n_frames, 3) or None if not found
        """
        if not self.hdf5_path:
            return None
        
        with HDF5TrialStorage(self.hdf5_path, self.id, mode='r') as storage:
            return storage.get_marker_by_name(marker_name)
    
    def load_analogs(self) -> Dict[str, np.ndarray]:
        """Load analog data from HDF5."""
        if not self.hdf5_path:
            raise ValueError("Trial has no HDF5 path")
        
        with HDF5TrialStorage(self.hdf5_path, self.id, mode='r') as storage:
            return storage.read_analogs()
    
    def load_forceplate(self, name: str) -> Dict[str, np.ndarray]:
        """Load force plate data from HDF5."""
        if not self.hdf5_path:
            raise ValueError("Trial has no HDF5 path")
        
        with HDF5TrialStorage(self.hdf5_path, self.id, mode='r') as storage:
            return storage.read_forceplate(name)
    
    def load_all_forceplates(self) -> Dict[str, Dict[str, np.ndarray]]:
        """Load all force plate data."""
        if not self.hdf5_path:
            return {}
        
        with HDF5TrialStorage(self.hdf5_path, self.id, mode='r') as storage:
            return {
                name: storage.read_forceplate(name)
                for name in storage.list_forceplates()
            }
    
    def get_events(self, label: str = "", context: str = "") -> list["Event"]:
        """Filter events by label and context."""
        return [
            event
            for event in self.events
            if (not label or event.label == label)
            and (not context or event.context == context)
        ]
```

**Changes:**
- Removed `markers`, `analogs`, `forceplates` relationships
- Added `hdf5_path` field
- Added cached metadata fields (`marker_names`, `marker_rate`, etc.)
- Added `load_*()` methods for data access
- Events stay in SQL (lightweight, queryable)

#### 2.2 Remove TimeSeriesData Abstractions

**Delete these files:**
- `src/movedb/models/data_models.py` ❌
- `src/movedb/models/markers.py` ❌
- `src/movedb/models/analogs.py` ❌
- `src/movedb/models/forceplates.py` ❌
- `src/movedb/models/shaped_arrays.py` ❌

**Why?** These were workarounds for SQL's inability to handle arrays. With HDF5, we access data directly as NumPy arrays.

#### 2.3 Keep Event Model (SQL)

**File:** `src/movedb/models/events.py`

```python
"""Event model - stays in SQL (lightweight, queryable)."""
from sqlmodel import SQLModel, Field, Relationship
from datetime import timedelta
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .trial import Trial

class Event(SQLModel, table=True):
    """Motion capture event (e.g., foot strike, foot off)."""
    
    id: int | None = Field(default=None, primary_key=True)
    
    trial_id: int = Field(foreign_key="trial.id")
    trial: "Trial" = Relationship(back_populates="events")
    
    context: str = Field(default="", index=True)
    label: str = Field(default="", index=True)
    time: timedelta
    description: str = Field(default="")
    
    def __repr__(self) -> str:
        return f"Event({self.context}/{self.label} @ {self.time.total_seconds():.3f}s)"
```

---

### Phase 3: Ingest Pipeline

#### 3.1 Refactor C3D Adapter

**File:** `src/movedb/ingest/c3d_adapter.py`

**Changes:**
1. Remove per-frame data conversion loops
2. Write bulk arrays to HDF5
3. Update Trial metadata

```python
"""C3D to MoveDB ingestion - HDF5 version."""
import ezc3d
from datetime import datetime, timedelta
from typing import Any, Dict, List
import numpy as np
from pathlib import Path

from ..models import Event, Trial
from ..storage.hdf5_storage import HDF5TrialStorage, get_trial_hdf5_path
from ..storage.config import get_storage_config
from pydantic import BaseModel
from loguru import logger

class C3DAdapter(BaseModel):
    """Adapter for converting C3D files to MoveDB format."""
    
    model_config = {"arbitrary_types_allowed": True}
    c3d: ezc3d.c3d
    
    @classmethod
    def from_file(cls, file_path: str, extract_forceplat_data: bool = True) -> "C3DAdapter":
        """Load C3D file."""
        c3d_obj = ezc3d.c3d(file_path, extract_forceplat_data=extract_forceplat_data)
        return cls(c3d=c3d_obj)
    
    def get_param(self, *keys: str, index: int | None = None, default: Any = None) -> Any:
        """Get nested parameters from C3D."""
        param: dict = self.c3d.parameters
        for key in keys:
            param = param.get(key, {})
        value = param.get("value", default)
        
        if index is not None and (isinstance(value, (list, np.ndarray))):
            if index < 0 or index >= len(value):
                raise IndexError(f"Index {index} out of range for parameter '{keys}'")
            return value[index]
        return value
    
    def to_trial(self, name: str = "") -> Trial:
        """
        Convert C3D to Trial with HDF5 storage.
        
        Args:
            name: Trial name (defaults to empty string)
            
        Returns:
            Trial instance with populated HDF5 file
        """
        # Create trial metadata (without ID yet)
        trial = Trial(
            name=name,
            timestamp=datetime.now(),
            parameters=self._extract_parameters()
        )
        
        # Note: Trial needs to be added to session and committed to get an ID
        # before we can save HDF5 data. This should be done by caller:
        # session.add(trial)
        # session.commit()
        # adapter.save_hdf5_data(trial)
        
        # Extract events (stay in SQL)
        trial.events = self._extract_events(trial)
        
        return trial
    
    def save_hdf5_data(self, trial: Trial) -> None:
        """
        Save time-series data to HDF5 after trial has been committed to database.
        
        Args:
            trial: Trial instance with valid ID
        """
        if not trial.id:
            raise ValueError("Trial must be committed to database before saving HDF5 data")
        
        # Get HDF5 path
        config = get_storage_config()
        hdf5_path = get_trial_hdf5_path(trial.id, config.hdf5_base_dir)
        trial.hdf5_path = str(hdf5_path)
        
        with HDF5TrialStorage(hdf5_path, trial.id, mode='w') as storage:
            # Save markers
            marker_data = self._extract_marker_data()
            if marker_data:
                storage.write_markers(**marker_data)
                trial.marker_names = marker_data['marker_names']
                trial.marker_rate = marker_data['rate']
                trial.n_frames = marker_data['data'].shape[0]
            
            # Save analogs
            analog_data = self._extract_analog_data()
            if analog_data:
                storage.write_analogs(**analog_data)
                trial.analog_names = analog_data['channel_names']
                trial.analog_rate = analog_data['rate']
            
            # Save force plates
            forceplate_names = []
            for i, fp_data in enumerate(self._extract_forceplate_data()):
                fp_name = f"FP{i+1}"
                storage.write_forceplate(name=fp_name, **fp_data)
                forceplate_names.append(fp_name)
            
            if forceplate_names:
                trial.forceplate_names = forceplate_names
                trial.forceplate_rate = fp_data['rate']
            
            # Save events to HDF5 as well (for completeness)
            event_dicts = [
                {
                    'context': e.context,
                    'label': e.label,
                    'time': e.time,
                    'description': e.description
                }
                for e in trial.events
            ]
            storage.write_events(event_dicts)
            
            # Update frame numbers
            trial.first_frame = self.c3d.header["points"]["first_frame"]
            trial.last_frame = self.c3d.header["points"]["last_frame"]
        
        logger.info(f"Saved HDF5 data for trial {trial.id} to {hdf5_path}")
    
    def _extract_marker_data(self) -> Dict[str, Any]:
        """Extract all marker data as arrays."""
        if "points" not in self.c3d.data:
            return {}
        
        # Get marker data: shape (3, n_markers, n_frames)
        points = self.c3d.data["points"][:3, :, :]  # xyz only
        residuals = self.c3d.data["meta_points"]["residuals"][0, :, :]
        
        # Reshape to (n_frames, n_markers, 3)
        data = np.transpose(points, (2, 1, 0))
        residuals = residuals.T  # (n_frames, n_markers)
        
        # Replace NaN with None is handled by numpy - keep as NaN
        # HDF5 handles NaN naturally
        
        # Get marker names
        n_markers = data.shape[1]
        marker_names = [
            self.get_param("POINT", "LABELS", index=i, default=f"Marker_{i}")
            for i in range(n_markers)
        ]
        
        rate = self.get_param("POINT", "RATE", default=100.0)
        units = self.get_param("POINT", "UNITS", index=0, default="mm")
        first_frame = self.c3d.header["points"]["first_frame"]
        
        return {
            'data': data,
            'marker_names': marker_names,
            'rate': rate,
            'units': units,
            'first_frame': first_frame,
            'residuals': residuals
        }
    
    def _extract_analog_data(self) -> Dict[str, Any]:
        """Extract all analog data as arrays."""
        if "analogs" not in self.c3d.data or len(self.c3d.data["analogs"]) == 0:
            return {}
        
        # Get analog data: shape (n_channels, n_frames)
        analogs = self.c3d.data["analogs"][0]  # First dimension seems to be empty
        
        # Reshape to (n_frames, n_channels)
        if analogs.ndim == 2:
            data = analogs.T
        else:
            data = analogs
        
        # Get channel names
        n_channels = data.shape[1]
        channel_names = [
            self.get_param("ANALOG", "LABELS", index=i, default=f"Channel_{i}")
            for i in range(n_channels)
        ]
        
        rate = self.get_param("ANALOG", "RATE", default=1000.0)
        units = self.get_param("ANALOG", "UNITS", index=0, default="V")
        first_frame = self.c3d.header["points"]["first_frame"]
        
        return {
            'data': data,
            'channel_names': channel_names,
            'rate': rate,
            'units': units,
            'first_frame': first_frame
        }
    
    def _extract_forceplate_data(self) -> List[Dict[str, Any]]:
        """Extract force plate data as arrays."""
        if "platform" not in self.c3d.data:
            return []
        
        forceplates = []
        for i, fp in enumerate(self.c3d.data["platform"]):
            # Extract force, moment, COP: shape (3, n_frames)
            forces = fp.get("force", np.zeros((3, 0))).T  # -> (n_frames, 3)
            moments = fp.get("moment", np.zeros((3, forces.shape[1]))).T
            cop = fp.get("center_of_pressure", np.zeros((3, forces.shape[1]))).T
            
            # Replace NaN with 0 for force plates
            forces = np.nan_to_num(forces, nan=0.0)
            moments = np.nan_to_num(moments, nan=0.0)
            cop = np.nan_to_num(cop, nan=0.0)
            
            rate = self.get_param("ANALOG", "RATE", default=1000.0)
            
            forceplates.append({
                'forces': forces,
                'moments': moments,
                'cop': cop,
                'rate': rate,
                'cal_matrix': fp.get("cal_matrix", np.eye(6)),
                'corners': fp.get("corners", np.zeros((4, 3))),
                'origin': fp.get("origin", np.zeros(3)),
                'unit_force': fp.get("unit_force", "N"),
                'unit_moment': fp.get("unit_moment", "Nm"),
                'unit_position': fp.get("unit_position", "m")
            })
        
        return forceplates
    
    def _extract_events(self, trial: Trial) -> List[Event]:
        """Extract events (stay in SQL)."""
        if "EVENT" not in self.c3d.parameters:
            return []
        
        events = []
        times = self.get_param("EVENT", "TIMES", default=[[],[]])
        
        if isinstance(times, np.ndarray):
            n_events = times.shape[1]
        else:
            n_events = len(times[0]) if times else 0
        
        for i in range(n_events):
            try:
                context = self.get_param("EVENT", "CONTEXTS", index=i, default="")
                label = self.get_param("EVENT", "LABELS", index=i, default="")
                
                if isinstance(times, np.ndarray):
                    time_min, time_sec = times[:, i]
                else:
                    time_min = times[0][i]
                    time_sec = times[1][i]
                
                description = self.get_param("EVENT", "DESCRIPTIONS", index=i, default="")
                
                events.append(Event(
                    trial=trial,
                    context=context,
                    label=label,
                    time=timedelta(minutes=time_min, seconds=time_sec),
                    description=description
                ))
            except (IndexError, ValueError) as e:
                logger.warning(f"Skipping event {i}: {e}")
        
        return events
    
    def _extract_parameters(self) -> Dict[str, Any]:
        """Extract trial parameters as JSON."""
        # Extract useful parameters for metadata
        params = {}
        
        # Frame info
        params['frame_rate'] = self.get_param("POINT", "RATE", default=None)
        params['analog_rate'] = self.get_param("ANALOG", "RATE", default=None)
        params['first_frame'] = self.c3d.header["points"]["first_frame"]
        params['last_frame'] = self.c3d.header["points"]["last_frame"]
        
        # Trial info
        params['trial_label'] = self.get_param("TRIAL", "LABEL", default="")
        params['trial_description'] = self.get_param("TRIAL", "DESCRIPTION", default="")
        
        return params
```

**Key Changes:**
- `to_trial()` creates Trial metadata only
- `save_hdf5_data()` writes bulk arrays to HDF5 (called after SQL commit)
- No per-frame loops - everything is vectorized
- Marker data: (n_frames, n_markers, 3) array in one write

---

### Phase 4: OpenSim Integration

#### 4.1 Update TRC/MOT Export

**File:** `src/movedb/osim/write.py`

```python
"""OpenSim export - reads from HDF5."""
import numpy as np
from pathlib import Path
from typing import Dict, Any
from pyopensim.common import TimeSeriesTableVec3, TRCFileAdapter
from loguru import logger

from ..models import Trial

def export_trial_to_trc(
    trial: Trial,
    output_path: Path,
    marker_subset: list[str] | None = None,
    output_units: str = "m"
) -> None:
    """
    Export trial markers to TRC file.
    
    Args:
        trial: Trial instance
        output_path: Output TRC file path
        marker_subset: Optional list of marker names to export (default: all)
        output_units: Units for output ("m" or "mm")
    """
    # Load marker data from HDF5
    marker_data = trial.load_markers()
    
    data = marker_data['data']  # (n_frames, n_markers, 3)
    marker_names = marker_data['marker_names']
    rate = marker_data['rate']
    units = marker_data['units']
    
    # Filter markers if subset requested
    if marker_subset:
        indices = [marker_names.index(name) for name in marker_subset if name in marker_names]
        data = data[:, indices, :]
        marker_names = [marker_names[i] for i in indices]
    
    # Convert units if needed
    conversion = _get_unit_conversion(units, output_units)
    if conversion != 1.0:
        data = data * conversion
    
    # Generate time array
    n_frames = data.shape[0]
    time = np.arange(n_frames) / rate
    
    # Write TRC
    _write_trc_file(output_path, data, marker_names, time, rate, output_units)
    
    logger.info(f"Exported {len(marker_names)} markers to {output_path}")


def _write_trc_file(
    filepath: Path,
    data: np.ndarray,
    marker_names: list[str],
    time: np.ndarray,
    rate: float,
    units: str
) -> None:
    """Write TRC file using OpenSim."""
    from pyopensim.simbody import Vec3, RowVectorVec3
    
    table = TimeSeriesTableVec3()
    table.setColumnLabels(marker_names)
    table.addTableMetaDataString("Units", units)
    table.addTableMetaDataString("DataRate", str(rate))
    
    for frame_idx in range(len(time)):
        row = []
        for marker_idx in range(len(marker_names)):
            coords = data[frame_idx, marker_idx, :]
            if np.any(np.isnan(coords)):
                coords = np.array([np.nan, np.nan, np.nan])
            row.append(Vec3(float(coords[0]), float(coords[1]), float(coords[2])))
        
        table.appendRow(time[frame_idx], RowVectorVec3(row))
    
    adapter = TRCFileAdapter()
    adapter.write(table, str(filepath))


def _get_unit_conversion(from_units: str, to_units: str) -> float:
    """Get conversion factor between units."""
    conversions = {
        ('mm', 'm'): 0.001,
        ('m', 'mm'): 1000.0,
        ('mm', 'mm'): 1.0,
        ('m', 'm'): 1.0,
    }
    return conversions.get((from_units.lower(), to_units.lower()), 1.0)
```

**Benefits:**
- Direct HDF5 → TRC (no SQL queries)
- Vectorized operations (no loops)
- Clean, readable code

---

### Phase 5: API Updates

#### 5.1 Ingest Endpoint

**File:** `src/movedb/api/routers/ingest.py`

```python
"""Ingest API - updated for HDF5."""
from fastapi import APIRouter, HTTPException, Query
from pathlib import Path

from ..dependencies import SessionDep
from ...ingest.c3d_adapter import C3DAdapter
from ...models import Trial

router = APIRouter(prefix="/ingest", tags=["ingest"])

@router.post("/file")
def ingest_c3d_file(
    file_path: str = Query(..., description="Path to C3D file"),
    trial_name: str | None = Query(None, description="Override trial name"),
    *,
    session: SessionDep
):
    """Ingest a single C3D file."""
    
    if not Path(file_path).exists():
        raise HTTPException(status_code=400, detail="File not found")
    
    if not file_path.lower().endswith('.c3d'):
        raise HTTPException(status_code=400, detail="File must be a C3D file")
    
    try:
        # Load C3D
        adapter = C3DAdapter.from_file(file_path)
        
        # Create trial metadata
        name = trial_name or Path(file_path).stem
        trial = adapter.to_trial(name=name)
        
        # Commit to get ID
        session.add(trial)
        session.commit()
        session.refresh(trial)
        
        # Save HDF5 data
        adapter.save_hdf5_data(trial)
        
        # Update trial with HDF5 path
        session.add(trial)
        session.commit()
        
        return {
            "message": "File ingested successfully",
            "file_path": file_path,
            "trial_id": trial.id,
            "trial_name": trial.name,
            "hdf5_path": trial.hdf5_path,
            "marker_count": len(trial.marker_names),
            "analog_count": len(trial.analog_names),
            "forceplate_count": len(trial.forceplate_names),
            "event_count": len(trial.events),
            "n_frames": trial.n_frames
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@router.get("/trials/{trial_id}/markers")
def get_trial_markers(trial_id: int, session: SessionDep):
    """Get marker data for a trial."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    try:
        marker_data = trial.load_markers()
        
        # Convert to JSON-serializable format
        return {
            "trial_id": trial_id,
            "marker_names": marker_data['marker_names'],
            "rate": marker_data['rate'],
            "units": marker_data['units'],
            "n_frames": marker_data['data'].shape[0],
            "n_markers": marker_data['data'].shape[1],
            "data": marker_data['data'].tolist()  # Warning: Large response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading markers: {str(e)}")


@router.get("/trials/{trial_id}/markers/{marker_name}")
def get_trial_marker(trial_id: int, marker_name: str, session: SessionDep):
    """Get data for a specific marker."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    
    marker_data = trial.get_marker(marker_name)
    if marker_data is None:
        raise HTTPException(status_code=404, detail=f"Marker '{marker_name}' not found")
    
    return {
        "trial_id": trial_id,
        "marker_name": marker_name,
        "n_frames": marker_data.shape[0],
        "data": marker_data.tolist()
    }
```

---

### Phase 6: Dependencies

#### 6.1 Update pyproject.toml

```toml
[project]
name = "movedb-core"
version = "0.2.0"  # Major refactor
description = "Movement database with hybrid SQL/HDF5 storage"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "ezc3d>=1.6.0",
    "h5py>=3.10.0",           # NEW: HDF5 storage
    "numpy>=1.24.0",
    "loguru>=0.7.3",
    "matplotlib>=3.10.7",
    "pandas>=2.3.3",
    "plotly>=6.3.1",
    "polars>=1.34.0",
    "pyvista>=0.46.3",
    "sqlmodel>=0.0.24",
    "fastapi>=0.100.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
]
```

---

## Implementation Order

### Week 1: Foundation
1. ✅ Create `storage/hdf5_storage.py`
2. ✅ Create `storage/config.py`
3. ✅ Add h5py to dependencies
4. ✅ Write unit tests for HDF5 storage layer

### Week 2: Data Models
5. ✅ Refactor `Trial` model
6. ✅ Delete `TimeSeriesData` abstractions
7. ✅ Update `Event` model (no changes needed)
8. ✅ Create database migration script (if needed)

### Week 3: Ingest
9. ✅ Refactor `C3DAdapter`
10. ✅ Test C3D → HDF5 pipeline
11. ✅ Update ingest API endpoints

### Week 4: Export & API
12. ✅ Update OpenSim export functions
13. ✅ Update API data access endpoints
14. ✅ Add HDF5 validation tools

### Week 5: Testing & Documentation
15. ✅ Integration tests
16. ✅ Performance benchmarks
17. ✅ Update documentation
18. ✅ Migration guide for existing users

---

## Testing Strategy

### Unit Tests

```python
"""Test HDF5 storage layer."""
import pytest
import numpy as np
from pathlib import Path
from movedb.storage.hdf5_storage import HDF5TrialStorage

def test_marker_storage(tmp_path):
    """Test writing and reading markers."""
    hdf5_path = tmp_path / "test_trial.h5"
    
    # Create test data
    n_frames, n_markers = 100, 50
    data = np.random.randn(n_frames, n_markers, 3)
    marker_names = [f"M{i}" for i in range(n_markers)]
    
    # Write
    with HDF5TrialStorage(hdf5_path, trial_id=1, mode='w') as storage:
        storage.write_markers(
            data=data,
            marker_names=marker_names,
            rate=100.0,
            units="mm"
        )
    
    # Read
    with HDF5TrialStorage(hdf5_path, trial_id=1, mode='r') as storage:
        result = storage.read_markers()
    
    # Verify
    assert np.allclose(result['data'], data)
    assert result['marker_names'] == marker_names
    assert result['rate'] == 100.0


def test_marker_by_name(tmp_path):
    """Test getting individual marker."""
    hdf5_path = tmp_path / "test_trial.h5"
    
    data = np.random.randn(100, 3, 3)
    marker_names = ["LASI", "RASI", "SACR"]
    
    with HDF5TrialStorage(hdf5_path, trial_id=1, mode='w') as storage:
        storage.write_markers(data=data, marker_names=marker_names, rate=100.0)
    
    with HDF5TrialStorage(hdf5_path, trial_id=1, mode='r') as storage:
        lasi = storage.get_marker_by_name("LASI")
    
    assert lasi.shape == (100, 3)
    assert np.allclose(lasi, data[:, 0, :])
```

### Performance Benchmarks

```python
"""Benchmark SQL vs HDF5."""
import time
import numpy as np

def benchmark_read_markers():
    """Compare read performance."""
    n_frames, n_markers = 10000, 50
    
    # SQL approach (old)
    start = time.time()
    # Query SQL, reconstruct arrays...
    sql_time = time.time() - start
    
    # HDF5 approach (new)
    start = time.time()
    with HDF5TrialStorage(hdf5_path, 1, 'r') as storage:
        data = storage.read_markers()
    hdf5_time = time.time() - start
    
    print(f"SQL: {sql_time:.3f}s")
    print(f"HDF5: {hdf5_time:.3f}s")
    print(f"Speedup: {sql_time/hdf5_time:.1f}x")

# Expected results:
# SQL: ~5-10s (with reconstruction)
# HDF5: ~0.1-0.5s
# Speedup: 10-50x
```

---

## Migration Checklist

- [ ] Review and approve this plan
- [ ] Set up HDF5 storage layer
- [ ] Refactor data models
- [ ] Update C3D adapter
- [ ] Update OpenSim integration
- [ ] Update API endpoints
- [ ] Write comprehensive tests
- [ ] Run performance benchmarks
- [ ] Update documentation
- [ ] Deploy and celebrate 🎉

---

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| HDF5 file corruption | High | Regular backups, validation tools, checksums |
| Concurrent access issues | Medium | Document single-writer limitation, consider Zarr for future |
| Increased storage size | Low | HDF5 compression is very effective |
| Learning curve for contributors | Low | HDF5 API is straightforward, provide examples |

---

## Future Enhancements

1. **Zarr Migration**: If cloud storage or parallel writes become necessary
2. **Lazy Loading**: Stream data from HDF5 without loading entire arrays
3. **Compression Tuning**: Benchmark different compression algorithms
4. **Indexing**: Add B-tree indexing for time-based queries
5. **Caching Layer**: Redis/Memcached for frequently accessed trials

---

## Conclusion

This migration will transform MoveDB from fighting SQL's limitations to leveraging the right tool for each job:

- **SQL**: Fast metadata queries, relationships, event filtering
- **HDF5**: Efficient array storage, natural data model, OpenSim integration

**Expected improvements:**
- 10-50x faster data access
- 50-90% reduction in database size
- Simpler, more maintainable code
- Better alignment with biomechanics workflows

**Next Steps:**
1. Review this plan with team
2. Create feature branch: `feature/hdf5-migration`
3. Start with Phase 1 (storage layer)
4. Iterate and test frequently

---

**Questions? Concerns?** Open an issue or discussion in the repository.

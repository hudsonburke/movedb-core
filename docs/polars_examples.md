# Polars DataFrame Analysis Examples

This guide demonstrates how to use Polars DataFrames for analyzing biomechanics data in MoveDB.

## Overview

MoveDB stores time-series data (markers, forceplates, analogs) in HDF5 format on disk. You can load this data either as:
- **NumPy arrays** (via `load_markers()`, `load_analogs()`, etc.) - for performance-critical operations
- **Polars DataFrames** (via `load_markers_df()`, `load_analogs_df()`, etc.) - for flexible analysis

## Type Definitions

The storage layer provides TypedDict schemas for type safety:

```python
from movedb.storage import MarkerData, AnalogData, ForceplateData

# These define the structure of dictionaries returned by load_* methods
```

## Loading Data as DataFrames

### Marker Data

```python
from movedb.models import Trial
import polars as pl

# Load trial
trial = Trial.get(session, trial_id=1)

# Long format: one row per (frame, marker)
df_long = trial.load_markers_df(format='long')
print(df_long.head())
# ┌──────┬───────┬─────────────┬────────┬────────┬────────┐
# │ time │ frame │ marker_name │ x      │ y      │ z      │
# ├──────┼───────┼─────────────┼────────┼────────┼────────┤
# │ 0.0  │ 0     │ RASI        │ 123.4  │ 456.7  │ 890.1  │
# │ 0.0  │ 0     │ LASI        │ -123.4 │ 456.7  │ 890.1  │
# │ 0.01 │ 1     │ RASI        │ 123.5  │ 456.8  │ 890.2  │
# └──────┴───────┴─────────────┴────────┴────────┴────────┘

# Wide format: one row per frame
df_wide = trial.load_markers_df(format='wide')
print(df_wide.head())
# ┌──────┬───────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐
# │ time │ frame │ RASI_x  │ RASI_y  │ RASI_z  │ LASI_x  │ LASI_y  │ LASI_z  │
# ├──────┼───────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┤
# │ 0.0  │ 0     │ 123.4   │ 456.7   │ 890.1   │ -123.4  │ 456.7   │ 890.1   │
# └──────┴───────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘
```

### Force Plate Data

```python
# Single force plate (wide format is typical)
df = trial.load_forceplate_df('FP1', format='wide')
print(df.columns)
# ['time', 'frame', 'fp_name', 'force_x', 'force_y', 'force_z', 
#  'moment_x', 'moment_y', 'moment_z', 'cop_x', 'cop_y', 'cop_z']

# All force plates combined
df_all = trial.load_all_forceplates_df(format='wide')
```

### Analog Data

```python
# EMG or other analog channels
df = trial.load_analogs_df(format='wide')

# Filter to EMG channels only
emg_cols = [col for col in df.columns if 'EMG' in col]
emg_df = df.select(['time'] + emg_cols)
```

## Analysis Examples

### 1. Filter Specific Markers

```python
# Long format makes filtering easy
df = trial.load_markers_df(format='long')

# Get data for right markers only
right_markers = df.filter(pl.col('marker_name').str.starts_with('R'))

# Get specific marker trajectory
rasi = df.filter(pl.col('marker_name') == 'RASI')
```

### 2. Calculate Velocities

```python
df = trial.load_markers_df(format='long')

# Calculate velocity for each marker
df = df.with_columns([
    (pl.col('x').diff() * trial.marker_rate).alias('vx'),
    (pl.col('y').diff() * trial.marker_rate).alias('vy'),
    (pl.col('z').diff() * trial.marker_rate).alias('vz'),
])

# Calculate speed (magnitude)
df = df.with_columns(
    speed=(pl.col('vx')**2 + pl.col('vy')**2 + pl.col('vz')**2).sqrt()
)
```

### 3. Analyze Force Plates

```python
df = trial.load_forceplate_df('FP1', format='wide')

# Calculate resultant force
df = df.with_columns(
    force_resultant=(
        pl.col('force_x')**2 + 
        pl.col('force_y')**2 + 
        pl.col('force_z')**2
    ).sqrt()
)

# Find peak vertical force
peak_force = df.select(pl.col('force_z').max()).item()
print(f"Peak vertical force: {peak_force:.2f} N")

# Detect foot contacts (when vertical force > threshold)
threshold = 50.0  # Newtons
contacts = df.filter(pl.col('force_z') > threshold)
```

### 4. Compare Multiple Force Plates

```python
df = trial.load_all_forceplates_df(format='wide')

# Calculate stats by force plate
stats = df.group_by('fp_name').agg([
    pl.col('force_z').max().alias('max_vertical_force'),
    pl.col('force_z').mean().alias('mean_vertical_force'),
    (pl.col('force_z') > 50).sum().alias('contact_frames'),
])
print(stats)
```

### 5. Time-Based Filtering

```python
df = trial.load_markers_df(format='long')

# Get data between 1.0 and 2.0 seconds
subset = df.filter(
    (pl.col('time') >= 1.0) & (pl.col('time') <= 2.0)
)

# Sample every 10th frame
downsampled = df.filter(pl.col('frame') % 10 == 0)
```

### 6. Joining Data Types

```python
# Load different data types
markers = trial.load_markers_df(format='wide')
fp = trial.load_forceplate_df('FP1', format='wide')

# Resample force plate data to match marker sampling rate
# (force plates often have higher sampling rate)
marker_times = markers['time'].to_list()
fp_resampled = fp.filter(
    pl.col('time').is_in(marker_times)
)

# Join on time
combined = markers.join(
    fp_resampled.select(['time', 'force_x', 'force_y', 'force_z']),
    on='time',
    how='left'
)
```

### 7. Export to Other Formats

```python
df = trial.load_markers_df(format='wide')

# Save to CSV
df.write_csv('marker_data.csv')

# Save to Parquet (efficient columnar format)
df.write_parquet('marker_data.parquet')

# Convert to Pandas if needed
pandas_df = df.to_pandas()

# Convert to NumPy
time = df['time'].to_numpy()
rasi_x = df['RASI_x'].to_numpy()
```

## Using Converters Directly

If you already have numpy data, you can convert it to Polars:

```python
from movedb.storage import markers_to_polars, forceplate_to_polars

# Load as numpy dict
marker_data = trial.load_markers()

# Convert to Polars
df_long = markers_to_polars(marker_data, format='long')
df_wide = markers_to_polars(marker_data, format='wide')
```

## Performance Tips

1. **Choose the right format:**
   - Use **long format** for filtering, grouping, and plotting individual markers/channels
   - Use **wide format** for matrix operations or when you need all markers at once

2. **Lazy evaluation:**
   ```python
   # Polars can optimize query plans with lazy evaluation
   df = trial.load_markers_df(format='long').lazy()
   result = (
       df.filter(pl.col('marker_name') == 'RASI')
       .select(['time', 'x', 'y', 'z'])
       .collect()  # Execute the query plan
   )
   ```

3. **Memory usage:**
   - For large trials, load only what you need
   - Use `.select()` to keep only required columns
   - Use `.filter()` early in the query chain

## Schema Reference

### MarkerData (TypedDict)
- `data`: ndarray (n_frames, n_markers, 3)
- `marker_names`: list[str]
- `rate`: float (Hz)
- `units`: str (e.g., 'mm')
- `first_frame`: int
- `residuals`: ndarray | None (n_frames, n_markers)

### AnalogData (TypedDict)
- `data`: ndarray (n_frames, n_channels)
- `channel_names`: list[str]
- `rate`: float (Hz)
- `units`: str (e.g., 'V')
- `first_frame`: int

### ForceplateData (TypedDict)
- `forces`: ndarray (n_frames, 3)
- `moments`: ndarray (n_frames, 3)
- `cop`: ndarray (n_frames, 3)
- `cal_matrix`: ndarray (6, 6)
- `corners`: ndarray (4, 3)
- `origin`: ndarray (3,)
- `rate`: float (Hz)
- `unit_force`, `unit_moment`, `unit_position`: str

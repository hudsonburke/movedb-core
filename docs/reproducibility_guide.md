---
id: reproducibility_guide
aliases: []
tags: []
---
# Reproducibility Guide for MoveDB Core

This guide explains how to use MoveDB Core's reproducibility features for biomechanics research, particularly thesis work requiring complete documentation and reproducible analyses.

## Overview

MoveDB Core provides four levels of reproducibility:

1. **Parameter Tracking**: All analysis settings saved as JSON
2. **Execution Provenance**: Complete metadata about analysis runs
3. **Analysis History**: Trial-level tracking of all performed analyses
4. **Reproduction Scripts**: Automated re-running of analyses

## Quick Start

### Basic Reproducible Analysis

```python
from movedb.osim.tools import IKSettings

# 1. Create settings
ik_settings = IKSettings(
    model_file="scaled_model.osim",
    marker_file="markers.trc",
    output_motion_file="ik_results.mot",
    accuracy=1e-5
)

# 2. Save settings for documentation
ik_settings.save_json("ik_settings.json")

# 3. Run analysis
ik_result = ik_settings.run()

# 4. Save complete provenance
ik_result.save_provenance("ik_provenance.json")

# 5. Record in trial history
trial.add_analysis_record("InverseKinematics", ik_settings.to_dict(), "ik_provenance.json")
```

## Detailed Workflow

### 1. Settings Serialization

All OpenSim tool settings support JSON serialization:

```python
from movedb.osim.tools import ScaleSettings, IKSettings, IDSettings

# Scaling settings
scale_settings = ScaleSettings(
    unscaled_model_path="generic.osim",
    marker_file="markers.trc",
    subject_mass=75.0
)
scale_settings.save_json("scale_settings.json")

# Inverse kinematics settings
ik_settings = IKSettings(
    model_file="scaled.osim",
    marker_file="markers.trc",
    accuracy=1e-5
)
ik_settings.save_json("ik_settings.json")

# Inverse dynamics settings
id_settings = IDSettings(
    model_file="scaled.osim",
    coordinates_file="ik_results.mot",
    external_loads_file="grf.xml"
)
id_settings.save_json("id_settings.json")
```

### 2. Provenance Tracking

Results automatically include complete execution metadata:

```python
# Run analysis
ik_result = ik_settings.run()

# Save provenance (includes settings, timing, success, warnings, etc.)
ik_result.save_provenance("ik_provenance.json")

# Provenance includes:
# - Tool name and version
# - Execution start/end times and duration
# - Success/failure status
# - All warnings and errors
# - Complete settings used
# - Output file paths
```

### 3. Trial Analysis History

Trials track all analyses performed:

```python
# Record analysis in trial history
trial.add_analysis_record(
    tool="InverseKinematics",
    settings=ik_settings.to_dict(),
    result_path="ik_provenance.json",
    success=True
)

# Query analysis history
all_analyses = trial.get_analysis_history()
ik_analyses = trial.get_analysis_history("InverseKinematics")

# Export complete history
trial.export_analysis_summary("trial_analysis_history.json")
```

### 4. Reproduction from Provenance

Re-run analyses with identical parameters:

```python
# Load settings from provenance
with open("ik_provenance.json") as f:
    provenance = json.load(f)

settings_data = provenance["settings"]
ik_settings = IKSettings(**settings_data)

# Modify output paths to avoid overwriting
ik_settings.output_motion_file = "reproduced_ik_results.mot"

# Re-run analysis
reproduced_result = ik_settings.run()
```

## Thesis Documentation

### Automatic Parameter Tables

Convert JSON settings to markdown tables for Methods sections:

```python
import json

def json_to_markdown_table(json_file: str, title: str) -> str:
    """Convert JSON settings to markdown table."""
    with open(json_file) as f:
        settings = json.load(f)
    
    table = f"## {title}\n\n"
    table += "| Parameter | Value |\n"
    table += "|-----------|-------|\n"
    
    for key, value in settings.items():
        table += f"| {key} | {value} |\n"
    
    return table

# Generate tables for thesis
scale_table = json_to_markdown_table("scale_settings.json", "Scaling Parameters")
ik_table = json_to_markdown_table("ik_settings.json", "Inverse Kinematics Parameters")
id_table = json_to_markdown_table("id_settings.json", "Inverse Dynamics Parameters")
```

### Execution Documentation

Use provenance files for complete execution documentation:

```python
def summarize_execution(provenance_file: str) -> dict:
    """Extract execution summary from provenance."""
    with open(provenance_file) as f:
        data = json.load(f)
    
    execution = data["execution"]
    return {
        "tool": data["tool"],
        "runtime_seconds": execution["run_time_seconds"],
        "success": execution["success"],
        "start_time": execution["start_time"],
        "end_time": execution["end_time"],
        "warnings": len(data.get("warnings", [])),
        "errors": len(data.get("errors", [])),
    }

# Document execution details
executions = [
    summarize_execution("scale_provenance.json"),
    summarize_execution("ik_provenance.json"),
    summarize_execution("id_provenance.json"),
]
```

## File Organization

### Recommended Directory Structure

```
thesis_results/
├── subject_01/
│   ├── trial_01/
│   │   ├── data/                    # HDF5 storage
│   │   ├── exports/                 # TRC, MOT, XML files
│   │   ├── opensim/                 # Scaled models, setups
│   │   ├── results/                 # Analysis outputs
│   │   │   ├── scale/              # Scaling results
│   │   │   ├── ik/                 # IK results
│   │   │   └── id/                 # ID results
│   │   ├── *_settings.json         # Parameter files
│   │   ├── *_provenance.json       # Execution records
│   │   ├── trial_metadata.json     # Trial information
│   │   ├── trial_history.json      # Analysis history
│   │   └── documentation/          # Thesis documentation
│   │       ├── analysis_summary.json
│   │       └── parameter_tables.md
```

### File Naming Convention

- `*_settings.json`: Analysis parameters (include in thesis)
- `*_provenance.json`: Complete execution metadata
- `trial_metadata.json`: Trial information
- `trial_history.json`: Analysis sequence
- `analysis_summary.json`: High-level summary

## Validation and Testing

### Reproducibility Validation

```python
# Test that settings are reproducible
original_settings = IKSettings.from_json("ik_settings.json")
reloaded_settings = IKSettings.from_json("ik_settings.json")

assert original_settings.to_dict() == reloaded_settings.to_dict()
assert original_settings.get_hash() == reloaded_settings.get_hash()
```

### Execution Validation

```python
# Test that results can be reconstructed
original_result = IKResult.from_provenance("ik_provenance.json")
reproduced_result = ik_settings.run()

# Compare key metrics
assert original_result.success == reproduced_result.success
assert abs(original_result.run_time - reproduced_result.run_time) < 1.0  # Allow 1s tolerance
```

## Best Practices

### For Thesis Work

1. **Save All Settings**: Use `save_json()` for every analysis
2. **Track Provenance**: Use `save_provenance()` for complete records
3. **Document History**: Use trial analysis history for complete workflows
4. **Version Control**: Include reproducibility files in git
5. **Parameter Tables**: Auto-generate from JSON for Methods sections

### For Reproducibility

1. **Use Relative Paths**: Avoid absolute paths in settings
2. **Timestamp Outputs**: Avoid overwriting by including timestamps
3. **Validate Results**: Compare reproduced vs original results
4. **Document Versions**: Include MoveDB and OpenSim versions
5. **Test Reproduction**: Regularly test that analyses can be reproduced

### For Collaboration

1. **Share Provenance**: Include provenance files with shared data
2. **Document Dependencies**: Note required OpenSim models and markersets
3. **Version Consistency**: Ensure same versions across reproductions
4. **Environment Setup**: Document required dependencies

## Troubleshooting

### Common Issues

**Settings not loading**: Check JSON syntax and required fields
**Provenance incomplete**: Ensure all result fields are populated
**Paths not resolving**: Use relative paths and consistent directory structure
**OpenSim errors**: Verify model and marker file compatibility

### Debugging

```python
# Check settings validity
try:
    settings = IKSettings.from_json("ik_settings.json")
    print("Settings loaded successfully")
except Exception as e:
    print(f"Settings error: {e}")

# Check provenance completeness
with open("ik_provenance.json") as f:
    data = json.load(f)

required_fields = ["tool", "execution", "settings", "outputs"]
missing = [f for f in required_fields if f not in data]
if missing:
    print(f"Missing provenance fields: {missing}")
```

## Advanced Usage

### Custom Analysis Pipelines

```python
class ReproduciblePipeline:
    """Custom analysis pipeline with reproducibility."""
    
    def __init__(self, trial: Trial):
        self.trial = trial
        self.results = {}
    
    def add_analysis(self, name: str, settings, result_path: str):
        """Add analysis to pipeline."""
        self.results[name] = {
            "settings": settings,
            "result_path": result_path,
        }
    
    def run_all(self):
        """Run all analyses with tracking."""
        for name, analysis in self.results.items():
            result = analysis["settings"].run()
            result.save_provenance(analysis["result_path"])
            self.trial.add_analysis_record(
                name, analysis["settings"].to_dict(), analysis["result_path"]
            )
    
    def export_documentation(self, output_dir: str):
        """Export complete documentation."""
        # Export settings, provenance, and summaries
        pass
```

### Batch Processing

```python
# Process multiple subjects/trials
subjects = ["subject_01", "subject_02", "subject_03"]

for subject in subjects:
    for trial_name in ["walking", "running"]:
        # Run reproducible pipeline
        pipeline = ReproduciblePipeline(trial)
        pipeline.run_all()
        pipeline.export_documentation(f"results/{subject}/{trial_name}")
```

This comprehensive reproducibility system ensures that biomechanics analyses are completely documented, reproducible, and suitable for academic publication requirements.


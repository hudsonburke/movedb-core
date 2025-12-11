# MoveDB Core

<img src="imgs/MoveDB-Logo-nobg-cropped.png" width="40%">

[![Tests](https://github.com/SOMA-Bionics/movedb-core/actions/workflows/tests.yml/badge.svg)](https://github.com/SOMA-Bionics/movedb-core/actions/workflows/tests.yml)
[![CI/CD](https://github.com/SOMA-Bionics/movedb-core/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/SOMA-Bionics/movedb-core/actions/workflows/ci-cd.yml)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Core library for movement database operations, including C3D file I/O and OpenSim integration.

## Features

- **C3D File I/O**: Read and process C3D motion capture files
- **OpenSim Integration**: Export data to OpenSim formats (TRC, MOT, XML)
- **Time Series Processing**: Handle marker trajectories and analog data
- **Force Platform Support**: Process force platform data from C3D files
- **Type Safety**: Full type hints and Pydantic models for data integrity

## Reproducibility Features

MoveDB Core provides comprehensive reproducibility features for biomechanics research

### Complete Workflow Tracking

```python
from movedb.osim.tools import IKSettings

# Settings are fully serializable
ik_settings = IKSettings(model="scaled.osim", marker_file="markers.trc")
ik_settings.save_json("ik_settings.json")  # Save for thesis Methods section

# Results include complete provenance
ik_result = ik_settings.run()
ik_result.save_provenance("ik_provenance.json")  # Complete execution record

# Trials track all analyses
trial.add_analysis_record("InverseKinematics", ik_settings.to_dict(), "ik_provenance.json")
```

### Key Features

- **Parameter Tracking**: All OpenSim settings saved as JSON for documentation
- **Execution Provenance**: Complete metadata including timing, success, warnings
- **Analysis History**: Trial-level tracking of all performed analyses
- **Reproducibility Scripts**: Re-run analyses with identical parameters
- **Thesis Documentation**: Automatic generation of parameter tables and summaries

### Example Workflow

See `examples/reproducible_opensim_workflow.py` for a complete C3D → Scale → IK → ID pipeline with full reproducibility tracking.

### Reproducing Analyses

Use `examples/reproduce_from_provenance.py` to re-run analyses from saved provenance files:

```bash
python examples/reproduce_from_provenance.py --provenance-dir thesis_results/subject_01/walking
```

### Documentation for Thesis

The reproducibility features automatically generate documentation suitable for thesis Methods sections:

- **Parameter Tables**: JSON settings files convert to markdown tables
- **Execution Details**: Provenance files provide complete analysis metadata
- **Analysis History**: Trial history tracks the complete analysis sequence
- **Reproducibility Reports**: Scripts validate that analyses can be reproduced

### Files Generated

A typical reproducible analysis creates:

```
thesis_results/
├── subject_01/
│   ├── walking/
│   │   ├── trial_metadata.json          # Trial information
│   │   ├── scale_settings.json          # Scaling parameters
│   │   ├── scale_provenance.json        # Scaling execution details
│   │   ├── ik_settings.json             # IK parameters
│   │   ├── ik_provenance.json           # IK execution details
│   │   ├── id_settings.json             # ID parameters
│   │   ├── id_provenance.json           # ID execution details
│   │   ├── trial_history.json           # Complete analysis history
│   │   └── documentation/
│   │       ├── analysis_summary.json    # Summary for thesis
│   │       └── parameter_tables.md      # Markdown tables for Methods
```

This ensures complete reproducibility and provides all necessary documentation for academic publications.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## FAQs

**Q: Why Python?**
A: Python is not the most performant language, but to maximize accessibility and ease of use, it is the best choice. Biomechanics researchers and practitioners often have limited programming experience, and Python's readability and extensive scientific libraries make it an ideal choice for this community. It also has a rich ecosystem of libraries for data analysis, machine learning, and scientific computing, which can be leveraged for advanced biomechanical analyses and reduces the need for researchers to reinvent the wheel. Particularly for this project, the use of SQLModel allows for a single codebase that can interact with both SQL databases and in-memory data structures seamlessly.

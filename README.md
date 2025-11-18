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

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## FAQs
**Q: Why Python?**
A: Python is not the most performant language, but to maximize accessibility and ease of use, it is the best choice. Biomechanics researchers and practitioners often have limited programming experience, and Python's readability and extensive scientific libraries make it an ideal choice for this community. It also has a rich ecosystem of libraries for data analysis, machine learning, and scientific computing, which can be leveraged for advanced biomechanical analyses and reduces the need for researchers to reinvent the wheel. Particularly for this project, the use of SQLModel allows for a single codebase that can interact with both SQL databases and in-memory data structures seamlessly.


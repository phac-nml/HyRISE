# HyRISE - HIV Resistance Interpretation & Scoring Engine

<p align="center">
  <img src="src/hyrise/core/assets/hyrise_logo.svg" alt="HyRISE Logo" width="300" height="auto"/>
</p>


<p align="center">
  <strong>A comprehensive tool for HIV drug resistance analysis and visualization developed by the National Microbiology Laboratory, Public Health Agency of Canada</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen?style=for-the-badge&logo=gitlab&logoColor=white&logoWidth=40&color=green" alt="Build Status">
  <img src="https://img.shields.io/badge/coverage-65.5%25-orange?style=for-the-badge&logo=codecov&logoColor=white&logoWidth=40&color=orange" alt="Coverage">
  <img src="https://img.shields.io/badge/python-3.8+-blue?style=for-the-badge&logo=python&logoColor=white&logoWidth=40&color=blue" alt="Python Versions">
  <img src="https://img.shields.io/pypi/dm/hyrise?style=for-the-badge&logo=pypi&logoColor=white&logoWidth=30&color=orange" alt="PyPI Downloads">
  <img src="https://img.shields.io/badge/license-GNU%20GPL%20v3-blue?style=for-the-badge&logo=gnu&logoColor=white&logoWidth=40&color=blue" alt="License">
</p>

## Overview

HyRISE (HIV Resistance Interpretation & Scoring Engine) is a specialized bioinformatics tool designed for analyzing HIV drug resistance profiles from genomic data. The software processes sequence data to identify mutations associated with antiretroviral drug resistance, calculates resistance scores, and generates comprehensive, interactive reports.

### Key Features

- **Comprehensive Resistance Analysis**: Process HIV sequence data to identify mutations associated with drug resistance across all major antiretroviral drug classes (NRTIs, NNRTIs, PIs, INSTIs)
- **Interactive Visualization**: Generate detailed, interactive visualizations of resistance profiles, mutation patterns, and clinical implications
- **MultiQC Integration**: Seamlessly integrates with MultiQC for producing publication-quality HTML reports
- **Sierra-Local Integration**: Built-in integration with Stanford's Sierra-Local for resistance prediction
- **Containerized Workflow**: Supports deployment via Singularity/Apptainer containers for reproducible analysis
- **Flexible Deployment Options**: Run natively or via containers with automatic dependency detection

## Installation Options

HyRISE can be installed and run in several ways:

1. **Direct Installation**: Install directly from PyPI or source
2. **Conda Environment**: Create a dedicated conda environment
3. **Container Execution**: Use the built-in Singularity/Apptainer container support

### Option 1: Direct Installation

HyRISE is available on PyPI and can be installed with pip:

```bash
pip install hyrise
```

To install from source:

```bash
git clone https://github.com/phac-nml/hyrise.git
cd hyrise
pip install -e .
```

### Option 2: Conda Environment Installation

For a clean, isolated environment, we recommend using conda/mamba:

```bash
# Create a new conda environment
conda create -n hyrise python=3.10

# Activate the environment
conda activate hyrise

# Install mamba for faster package management
conda install -c conda-forge mamba

# Install HyRISE and its dependencies
mamba install -c conda-forge -c bioconda hyrise

# Alternatively, install from PyPI within the environment
pip install hyrise
```

### Option 3: Singularity/Apptainer Container Setup

For reproducible analysis or to avoid dependency conflicts, you can use HyRISE's container support:

#### Step 1: Install Singularity/Apptainer

If you don't have Singularity (now called Apptainer) installed, you have two options:

**Option A: Using conda/mamba (recommended for HPC environments without sudo access)**

```bash
# Create a conda environment if you haven't already
conda create -n hyrise python=3.10
conda activate hyrise

# Install mamba for faster package management
conda install -c conda-forge mamba

# Install Apptainer using mamba
mamba install -c conda-forge -c bioconda apptainer
```

**Option B: System-wide installation (requires sudo access)**

```bash
# On Debian/Ubuntu systems
sudo apt-get update
sudo apt-get install -y apptainer

# On CentOS/RHEL
sudo yum install -y apptainer
```

For other operating systems, please refer to the [Apptainer documentation](https://apptainer.org/docs/admin/main/installation.html).

#### Step 2: Install HyRISE

Install HyRISE as a Python package:

```bash
pip install hyrise
```

#### Step 3: Build the Container

HyRISE provides a command to build the container:

```bash
# Check if container support is working
hyrise check-deps

# Build the container
hyrise container

# OR if you need sudo access to build the container
hyrise container --sudo
```

The container will be built from the definition file packaged with HyRISE.

## Dependencies

HyRISE requires the following external tools:

- **Python 3.8+**: The base requirement
- **MultiQC**: For generating HTML reports
- **Sierra-Local**: For processing HIV sequence data
- **Singularity/Apptainer** (optional): For container-based execution

When using the container, all dependencies are packaged together, eliminating the need for separate installations.

## Usage Guide

### Command Line Interface

HyRISE provides a comprehensive command-line interface:

```bash
# Display help information
hyrise --help

# Process a Sierra JSON file and create visualization files
hyrise process -i input_file.json -o output_directory

# Generate and run the full MultiQC report
hyrise process -i input_file.json -o output_directory --report --run-multiqc

# Specify a sample name
hyrise process -i input_file.json -o output_directory -s "Sample123" --run-multiqc

# Check dependencies and container status
hyrise check-deps
```

### Processing HIV Sequence Files

To analyze FASTA files directly:

```bash
# Process a FASTA file using SierraLocal and generate a report
hyrise sierra RT.fasta --process --run-multiqc

# Process multiple FASTA files
hyrise sierra gene1.fasta gene2.fasta --process-dir results --run-multiqc
```

### Container Options

HyRISE automatically detects if dependencies are missing and uses the container if available. You can also explicitly control container usage:

```bash
# Force using the container
hyrise process -i input.json -o output_dir --container

# Force using local dependencies
hyrise process -i input.json -o output_dir --no-container

# Specify a custom container path
hyrise process -i input.json -o output_dir --container-path /path/to/custom/hyrise.sif
```

### Building and Managing Containers

```bash
# Build the HyRISE Singularity container
hyrise container

# Extract the definition file without building
hyrise container --extract-def my_directory

# Build with sudo (may be required on some systems)
hyrise container --sudo
```

### Python API

HyRISE can also be used as a Python library:

```python
from hyrise import process_files

# Process a single file
process_files(
    json_file="path/to/sierra_output.json",
    output_dir="path/to/output_dir",
    sample_name="Optional_Sample_ID",
    generate_report=True,
    run_multiqc=True
)

# Use container execution
process_files(
    json_file="path/to/sierra_output.json",
    output_dir="path/to/output_dir",
    use_container=True
)
```

## Available Commands

HyRISE provides several subcommands:

- `process`: Process Sierra JSON files to generate visualizations
- `check-deps`: Check for dependencies and container availability
- `container`: Build or manage the Singularity container
- `sierra`: Process FASTA files using SierraLocal to generate JSON files

Each command has its own help menu. For example:

```bash
hyrise process --help
hyrise sierra --help
```

## Output

HyRISE generates several types of output:

1. **MultiQC Custom Content Files**: JSON and HTML files that can be integrated into MultiQC reports
2. **MultiQC Configuration File**: Configuration for report generation
3. **MultiQC Report**: Interactive HTML report with visualizations (when `--run-multiqc` is specified)

The report includes:

- Resistance profiles for each gene (PR, RT, IN)
- Mutation tables and position maps
- Clinical commentary on resistance implications
- Resistance level distribution visualizations
- Metadata and version information

## Customization

### Adding New Visualizations

To add a new visualization type:

1. Create a new function in one of the visualizer modules or create a new module
2. Import and call your function from `hyrise/core/processor.py`

### Modifying Existing Visualizations

Each visualization is contained in its own function, making it easy to modify without affecting other parts of the system:

- Resistance-related visualizations: `hyrise/visualizers/resistance.py`
- Mutation-related visualizations: `hyrise/visualizers/mutations.py`
- Metadata visualizations: `hyrise/visualizers/metadata.py`
- Interpretation guides: `hyrise/visualizers/interpretation.py`

## Package Structure

```
hyrise/                  # Main package directory
├── __init__.py          # Package initialization
├── cli.py               # Command line interface 
├── hyrise.def           # Singularity container definition file
├── core/                # Core functionality
│   ├── __init__.py
│   ├── file_utils.py    # File handling utilities
│   ├── processor.py     # Main processing logic
│   └── report_config.py # MultiQC report configuration
├── visualizers/         # Visualization modules
│   ├── __init__.py
│   ├── hiv_visualizations.py # HIV-specific visualizations
│   └── info_and_guides.py # Interpretation guides and metadata
├── commands/            # Command modules
│   ├── __init__.py
│   ├── container.py     # Container management commands
│   └── sierra.py        # SierraLocal integration commands
└── utils/               # Utility functions
    ├── __init__.py
    ├── common_args.py   # Common argument parsers
    ├── html_utils.py    # HTML generation utilities
    ├── container_utils.py # Container detection and execution
    └── container_builder.py # Container installation
```

## Troubleshooting

### Common Issues

1. **Missing Dependencies**:
   - Run `hyrise check-deps` to see which dependencies are missing
   - Use the container option with `--container` to avoid dependency issues

2. **Container Build Failures**:
   - Ensure Singularity/Apptainer is installed
   - Try using `--sudo` if you have permission issues
   - Check disk space (container build requires ~1GB free space)

3. **SierraLocal Issues**:
   - The first run may be slow as it downloads the HIVDB database
   - Use `--forceupdate` to update the HIVDB database

### Getting Help

Run any command with `--help` to see detailed usage information:

```bash
hyrise --help
hyrise process --help
hyrise sierra --help
hyrise container --help
hyrise check-deps --help
```

## Citing HyRISE

If you use HyRISE in your research, please cite it as follows:

```
Osahan, G., Ji, H., et al. (2025). HyRISE: HIV Resistance Interpretation & Scoring Engine — A pipeline for HIV drug resistance analysis and visualization. National Microbiology Laboratory, Public Health Agency of Canada. https://github.com/phac-nml/hyrise
```

For BibTeX:

```bibtex
@software{hyrise_2025,
  author       = {Osahan, Gurasis and Ji, Hezhao},
  title        = {HyRISE: HIV Resistance Interpretation \& Scoring Engine — A pipeline for HIV drug resistance analysis and visualization},
  year         = {2025},
  publisher    = {Public Health Agency of Canada},
  version      = {0.1.1},
  url          = {https://github.com/phac-nml/hyrise},
  organization = {National Microbiology Laboratory, Public Health Agency of Canada},
}
```

## License

HyRISE is distributed under the **GNU General Public License v3.0**. Refer to the [GNU GPL v3.0](https://www.gnu.org/licenses/gpl-3.0.html) for the full terms and conditions.

## Support and Contact

- **Issue Tracking**: Report issues and feature requests on our [GitHub repository](https://github.com/phac-nml/hyrise)
- **Documentation**: Additional documentation is available in the docs/ directory
- **Email Support**: [Gurasis Osahan](mailto:gurasis.osahan@phac-aspc.gc.ca)

---

> **Thank you for using HyRISE!**  
> We welcome feedback and contributions to improve this tool.
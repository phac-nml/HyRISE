# HyRISE - HIV Resistance Interpretation & Scoring Engine

<p align="center">
  <picture>
    <!-- Try local repo path first -->
    <source srcset="src/hyrise/core/assets/hyrise_logo.svg" type="image/svg+xml">
    <!-- Fallback to raw GitHub URL -->
    <img src="https://raw.githubusercontent.com/phac-nml/HyRISE/main/src/hyrise/core/assets/hyrise_logo.svg"
         alt="HyRISE Logo" width="300" />
  </picture>
</p>


<p align="center">
  <strong>A tool for HIV drug resistance analysis and visualization developed by the National Microbiology Laboratory, Public Health Agency of Canada</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/build-passing-brightgreen?style=for-the-badge&logo=gitlab&logoColor=white&logoWidth=40&color=green" alt="Build Status">
  <img src="https://img.shields.io/badge/coverage-58.6%25-orange?style=for-the-badge&logo=codecov&logoColor=white&logoWidth=40&color=orange" alt="Coverage">
  <img src="https://img.shields.io/badge/python-3.9+-blue?style=for-the-badge&logo=python&logoColor=white&logoWidth=40&color=blue" alt="Python Versions">
  <img src="https://img.shields.io/pypi/dm/hyrise?style=for-the-badge&logo=pypi&logoColor=white&logoWidth=30&color=orange" alt="PyPI Downloads">
  <img src="https://img.shields.io/badge/license-GNU%20GPL%20v3-blue?style=for-the-badge&logo=gnu&logoColor=white&logoWidth=40&color=blue" alt="License">
</p>

## Overview

HyRISE (HIV Resistance Interpretation & Scoring Engine) is a command-line tool for HIV drug resistance interpretation and reporting.

It supports two primary workflows:

1. `process`: convert Sierra JSON results into MultiQC custom content (`*_mqc.json`, `*_mqc.html`), with built-in report generation support.
2. `sierra`: run SierraLocal on FASTA input and optionally chain directly into `process`.

The CLI is deterministic by default (no implicit interactive mode), with optional guided mode via `--interactive`.

## Installation

### PyPI

```bash
pip install hyrise
```

### From Source

```bash
git clone https://github.com/phac-nml/HyRISE
cd HyRISE
pip install -e .
```

### Conda Environment

```bash
conda create -n hyrise python=3.11
conda activate hyrise
pip install hyrise
```

## Quickstart

Use de-identified fixtures from `example_data/public/`.

### 1) Process a Sierra JSON file

```bash
hyrise process -i example_data/public/DEMO_IN_NGS_results.json --out out
```

### 2) Process IN + PRRT together

```bash
hyrise process \
  example_data/public/DEMO_IN_NGS_results.json \
  example_data/public/DEMO_PRRT_NGS_results.json \
  --out out
```

### 3) FASTA to Sierra JSON, then process

```bash
hyrise sierra example_data/public/DEMO_IN_NGS.fasta --process --process-dir out
```

## Process Report Flags

- `--report` (`-r`): generate report configuration assets.
- `--run-multiqc`: run MultiQC and generate the final report.
- `--run-multiqc` automatically enables `--report`.

Example (full report generation):

```bash
hyrise process -i example_data/public/DEMO_IN_NGS_results.json --out out --run-multiqc
```

## Process Command Options

`hyrise process` supports the following inputs and flags:

- `-i, --input`: single Sierra JSON input file.
- positional `inputs`: one or more Sierra JSON input files.
- `-o, --output-dir, --output_dir, --out`: output directory (required).
- `-s, --sample_name`: override sample name in outputs/report.
- `-r, --report`: generate report configuration assets.
- `--run-multiqc`: run MultiQC and generate final report (`--report` is implied).
- `--guide`: include interpretation guide content.
- `--sample-info`: include sample information section.
- `-e, --email`: contact email for report header.
- `-l, --logo`: custom logo path (PNG/SVG).
- `--container`: force container execution.
- `--no-container`: force native execution.
- `--container-path`: explicit `.sif` path.
- `--container-runtime {apptainer,singularity}`: choose runtime explicitly.
- `--config`: custom HyRISE TOML config path.
- `-I, --interactive`: guided interactive prompt mode.

## Command Summary

- `hyrise process`: process Sierra JSON into report-ready outputs.
- `hyrise sierra`: run SierraLocal on FASTA input.
- `hyrise container`: pull/build/extract container assets.
- `hyrise resources`: update/list HIVdb resource files.
- `hyrise check-deps`: show native/container dependency status.

Help:

```bash
hyrise --help
python -m hyrise --help
hyrise process --help
hyrise sierra --help
hyrise container --help
hyrise resources --help
hyrise check-deps --help
```

## Python API

HyRISE is CLI-first. For Python usage, keep imports explicit:

```python
from hyrise.core.processor import process_files
```

Stable top-level API is intentionally minimal:

```python
import hyrise
print(hyrise.__version__)
```

## Inputs and Outputs

### Accepted Inputs

- `process`: one or more Sierra JSON files
- `sierra`: one or more FASTA files

### Outputs

- `*_mqc.json`
- `*_mqc.html`
- MultiQC report output when `--run-multiqc` is enabled (`--run-multiqc` implies `--report`)

## Container Workflows

### Recommended on HPC: pull prebuilt image

```bash
hyrise container --pull --output hyrise.sif --image ghcr.io/phac-nml/hyrise:latest
hyrise process -i example_data/public/DEMO_IN_NGS_results.json --out out --container --container-path ./hyrise.sif
```

### Build Apptainer/Singularity image locally from pip-installed assets

```bash
hyrise container --extract-def container_build
apptainer build hyrise.sif container_build/hyrise.def
# or: singularity build hyrise.sif container_build/hyrise.def
```

### Build Docker image from pip-installed assets

```bash
hyrise container --extract-dockerfile container_build
docker build -f container_build/Dockerfile -t hyrise:local container_build
docker run --rm -v "$PWD:/data" hyrise:local --help
```

### Build Docker image from repository source

```bash
docker build -f src/hyrise/Dockerfile -t hyrise:local .
```

### Private Registry Note

If the repository is private but the package is published on PyPI, `pip install hyrise` still works without repository access.

Container pull depends on registry access:

- public registry image: no extra credentials required
- private registry image: users must authenticate
- offline or restricted environments: provide a local `.sif` and use `--container-path`

## Interactive Mode

Interactive mode is explicit and optional:

```bash
hyrise --interactive
hyrise process --interactive
hyrise sierra --interactive
hyrise container --interactive
hyrise check-deps --interactive
```

## Configuration

Configuration precedence:

1. CLI flags
2. config file
3. optional environment overrides
4. built-in defaults

Default config path:

```text
~/.config/hyrise/config.toml
```

Example:

```toml
[container]
path = "/path/to/hyrise.sif"
runtime = "apptainer"
search_paths = ["/shared/containers/hyrise.sif"]

[resources]
dir = "/path/to/hyrise/resources"
```

## Resource Updates and Offline Behavior

- Normal analysis runs do not download resources.
- Downloads occur only when explicitly requested:
  - `hyrise resources --update-hivdb`
  - `hyrise resources --update-apobec`
  - `hyrise resources --update-all`
- After resource update, `hyrise sierra` automatically prefers the newest downloaded `HIVDB_*.xml` when default `--xml` is used.

```bash
hyrise resources --list
hyrise resources --update-hivdb
```

## Troubleshooting

### Missing `sierralocal`

- Install natively: `pip install sierralocal post-align`
- Or use container mode: `hyrise sierra <input.fasta> --container --container-path /path/to/hyrise.sif`
- For HPC: `apptainer pull hyrise.sif docker://ghcr.io/phac-nml/hyrise:latest`

### Missing `multiqc`

`multiqc` is installed with `hyrise` by default. If it is missing, reinstall HyRISE in a clean environment:

```bash
pip install --upgrade --force-reinstall hyrise
```

### Container runtime not found

Install Apptainer/Singularity, or pass an explicit runtime with `--container-runtime`.

## Compatibility

- Python: 3.9, 3.10, 3.11, 3.12
- Container runtimes: Apptainer and Singularity
- Entry points: `hyrise` and `python -m hyrise`

## Citing HyRISE

If you use HyRISE in your research, please cite it as follows:

```
Osahan, G., Ji, H., et al. (2026). HyRISE: HIV Resistance Interpretation & Scoring Engine — A pipeline for HIV drug resistance analysis and visualization. National Microbiology Laboratory, Public Health Agency of Canada. https://github.com/phac-nml/hyrise
```

For BibTeX:

```bibtex
@software{hyrise_2026,
  author       = {Osahan, Gurasis and Ji, Hezhao},
  title        = {HyRISE: HIV Resistance Interpretation \& Scoring Engine — A pipeline for HIV drug resistance analysis and visualization},
  year         = {2026},
  publisher    = {Public Health Agency of Canada},
  version      = {0.2.1},
  url          = {https://github.com/phac-nml/hyrise},
  organization = {National Microbiology Laboratory, Public Health Agency of Canada},
}
```

## License

HyRISE is distributed under the **GNU General Public License v3.0**. Refer to the [GNU GPL v3.0](https://www.gnu.org/licenses/gpl-3.0.html) for the full terms and conditions.

## Support and Contact

- **Issue Tracking**: Report issues and feature requests on your project tracker
- **Email Support**: [Gurasis Osahan](mailto:gurasis.osahan@phac-aspc.gc.ca)

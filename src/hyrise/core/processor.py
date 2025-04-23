# hyrise/core/processor.py
"""
Main processing logic for HyRISE package

This module implements the core processing functionality for analyzing HIV drug resistance
from Sierra JSON output files and generating comprehensive visualizations and reports.
"""
import os
import tempfile
import shutil
import subprocess
import json
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

from hyrise.core.file_utils import extract_sample_id, load_json_file
from hyrise.core.report_config import HyRISEReportGenerator
from hyrise.utils.container_utils import ensure_dependencies
from hyrise.visualizers.hiv_visualizations import (
    # Mutation visualizations
    create_mutation_details_table,
    create_mutation_position_visualization,
    create_mutation_type_summary,
    # Resistance visualizations
    create_drug_resistance_profile,
    create_drug_class_resistance_summary,
    # Mutation-resistance impact visualizations
    create_mutation_resistance_contribution,
    create_mutation_clinical_commentary,
)
from hyrise.visualizers.info_and_guides import (
    create_unified_report_section,
    create_sample_analysis_info,
)
from hyrise import __version__


def process_files(
    json_file: str,
    output_dir: str,
    sample_name: Optional[str] = None,
    generate_report: bool = False,
    run_multiqc: bool = False,
    guide: bool = False,
    sample_info: bool = False,
    contact_email: Optional[str] = None,
    logo_path: Optional[str] = None,
    use_container: Optional[bool] = None,
    container_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Process Sierra JSON file to create MultiQC visualizations and reports.

    This function handles the complete workflow for processing one or more HIV sequences
    from a Sierra JSON file, generating visualizations, and optionally creating a
    MultiQC report.

    Args:
        json_file: Path to the Sierra JSON file
        output_dir: Directory where output files will be created
        sample_name: Sample name to use in the report.
            If not provided, it will be extracted from the filename.
        generate_report: Whether to generate a MultiQC config file
        run_multiqc: Whether to run MultiQC to generate the report
        guide: Whether to include interpretation guides
        sample_info: Whether to include sample information
        contact_email: Contact email to include in the report
        logo_path: Path to custom logo file
        use_container: Whether to use Singularity container.
            If None, auto-detect based on dependencies. If True, force container.
            If False, force native execution.
        container_path: Path to the Singularity container

    Returns:
        dict: Summary of the processing results including paths to generated files,
              processed sequences, and execution details
    """
    # Initialize result tracking
    results = initialize_results(json_file, output_dir)

    try:
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Check dependencies and container availability
        deps = check_dependencies(use_container, container_path, results)

        # Get sample name - use provided name or extract from filename
        if not sample_name:
            sample_name = extract_sample_id(json_file)

        results["sample_name"] = sample_name

        # Process JSON data and generate visualizations
        all_metadata = process_sequences(
            json_file, output_dir, sample_name, guide, sample_info, results
        )

        # Collect all generated visualization files
        collect_generated_files(output_dir, results)

        # Generate report if requested
        if generate_report:
            generate_multiqc_report(
                json_file,
                output_dir,
                sample_name,
                all_metadata,
                contact_email,
                logo_path,
                run_multiqc,
                deps,
                results,
            )

        # Print summary information
        print_processing_summary(results)

        return results

    except FileNotFoundError as e:
        handle_error(f"Input file not found: {e}", results)
        return results
    except json.JSONDecodeError as e:
        handle_error(f"Invalid JSON format in input file: {e}", results)
        return results
    except Exception as e:
        handle_error(
            f"Error processing file {json_file}: {e}", results, include_traceback=True
        )
        return results


def initialize_results(json_file: str, output_dir: str) -> Dict[str, Any]:
    """Initialize the results dictionary with basic information."""
    return {
        "json_file": os.path.abspath(json_file),
        "output_dir": os.path.abspath(output_dir),
        "files_generated": [],
        "processed_sequences": [],
        "skipped_sequences": [],
        "config_file": None,
        "report_dir": None,
        "multiqc_command": None,
        "container_used": False,
        "success": True,
        "error": None,
    }


def check_dependencies(
    use_container: Optional[bool],
    container_path: Optional[str],
    results: Dict[str, Any],
) -> Dict[str, Any]:
    """Check dependencies and container availability."""
    try:
        # Check dependencies and container availability
        deps = ensure_dependencies(use_container)

        # Override container path if specified and exists
        if container_path and os.path.exists(container_path):
            deps["container_path"] = container_path

        results.update({"dependencies": deps, "container_used": deps["use_container"]})
        return deps
    except Exception as e:
        results["success"] = False
        results["error"] = f"Error checking dependencies: {str(e)}"
        raise


def process_sequences(
    json_file: str,
    output_dir: str,
    sample_name: str,
    guide: bool,
    sample_info: bool,
    results: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Process each sequence in the JSON file and generate visualizations.

    Args:
        json_file: Path to the Sierra JSON file
        output_dir: Directory for output files
        sample_name: Sample name for the report
        guide: Whether to include interpretation guides
        sample_info: Whether to include sample information
        results: Results dictionary to update

    Returns:
        List of metadata dictionaries for all processed sequences
    """
    try:
        # Load the data, preserving list structure
        data_list = load_json_file(json_file, preserve_list=True)

        # If it's not a list, make it one for consistent processing
        if not isinstance(data_list, list):
            data_list = [data_list]

        # Track all metadata for report generation
        all_metadata = []

        # Process each item in the list
        for idx, data_item in enumerate(data_list):
            # Get sequence header for logging
            sequence_header = data_item.get("inputSequence", {}).get(
                "header", f"Sequence_{idx + 1}"
            )
            # Skip entries with no gene data
            if not data_item.get("alignedGeneSequences") and not data_item.get(
                "drugResistance"
            ):
                print(f"Skipping sequence with no gene data: {sequence_header}")
                results["skipped_sequences"].append(sequence_header)
                continue

            # For successful sequences, proceed with processing
            results["processed_sequences"].append(sequence_header)

            # Get formatted date for the report
            formatted_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Extract metadata for this sequence
            metadata = extract_metadata(data_item, sample_name)
            all_metadata.append(metadata)

            try:
                # Generate all visualizations for this sequence
                create_drug_resistance_profile(data_item, sample_name, output_dir)
                create_drug_class_resistance_summary(data_item, sample_name, output_dir)

                # Generate mutation-resistance impact visualizations
                create_mutation_resistance_contribution(
                    data_item, sample_name, output_dir
                )
                create_mutation_clinical_commentary(data_item, sample_name, output_dir)
                create_mutation_details_table(data_item, sample_name, output_dir)
                create_mutation_position_visualization(
                    data_item, sample_name, output_dir
                )
                create_mutation_type_summary(data_item, sample_name, output_dir)

                # Generate metadata information if requested
                if guide:
                    create_unified_report_section(
                        data_item, sample_name, formatted_date, output_dir
                    )

                # Process sample information if requested
                if sample_info:
                    create_sample_analysis_info(
                        data_item, sample_name, formatted_date, output_dir
                    )

            except Exception as e:
                print(f"Error processing sequence {sequence_header}: {str(e)}")
                # Continue processing other sequences even if one fails

        return all_metadata

    except Exception as e:
        results["success"] = False
        results["error"] = f"Error processing sequences: {str(e)}"
        raise


def extract_metadata(data_item: Dict[str, Any], sample_name: str) -> Dict[str, Any]:
    """Extract relevant metadata from a sequence for report generation."""
    # Extract database version information
    db_version = None
    db_publish_date = None

    for dr in data_item.get("drugResistance", []):
        if "version" in dr:
            db_version = dr["version"].get("text", "Unknown")
            db_publish_date = dr["version"].get("publishDate", "Unknown")
            break  # Use the first available version

    # Extract gene information
    genes = {}
    for gene_seq in data_item.get("alignedGeneSequences", []):
        gene_name = gene_seq["gene"]["name"]
        first_aa = gene_seq.get("firstAA", 0)
        last_aa = gene_seq.get("lastAA", 0)
        length = (last_aa - first_aa + 1) if first_aa and last_aa else 0

        genes[gene_name] = {
            "first_aa": first_aa,
            "last_aa": last_aa,
            "length": length,
            "mutations_count": len(gene_seq.get("mutations", [])),
            "sdrm_count": len(gene_seq.get("SDRMs", [])),
        }

    # Create metadata structure
    return {
        "sample_id": sample_name,
        "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sequence_header": data_item.get("inputSequence", {}).get("header", "Unknown"),
        "subtype": data_item.get("subtypeText", "Unknown"),
        "database": {
            "version": db_version or "Unknown",
            "publish_date": db_publish_date or "Unknown",
        },
        "genes": genes,
        "validation": data_item.get("validationResults", []),
    }


def collect_generated_files(output_dir: str, results: Dict[str, Any]) -> None:
    """Collect all generated visualization files."""
    for root, _, files in os.walk(output_dir):
        for file in files:
            if file.endswith("_mqc.json") or file.endswith("_mqc.html"):
                results["files_generated"].append(os.path.join(root, file))


def generate_multiqc_report(
    json_file: str,
    output_dir: str,
    sample_name: str,
    all_metadata: List[Dict[str, Any]],
    contact_email: Optional[str],
    logo_path: Optional[str],
    run_multiqc: bool,
    deps: Dict[str, Any],
    results: Dict[str, Any],
) -> None:
    """
    Generate MultiQC report for the processed sequences.

    Args:
        json_file: Path to the Sierra JSON file
        output_dir: Directory for output files
        sample_name: Sample name for the report
        all_metadata: Metadata from all processed sequences
        contact_email: Contact email for the report
        logo_path: Path to custom logo file
        run_multiqc: Whether to run MultiQC
        deps: Dependencies information
        results: Results dictionary to update
    """
    try:
        # Merge metadata from all sequences for a comprehensive report
        combined_metadata = merge_metadata(all_metadata)

        # Initialize report generator class
        report_generator = HyRISEReportGenerator(
            output_dir=output_dir,
            version=__version__,
            sample_name=sample_name,
            metadata_info=combined_metadata,
            contact_email=contact_email,
        )

        # Store report directory for results
        report_dir = os.path.join(output_dir, "multiqc_report")
        results["report_dir"] = report_dir

        if run_multiqc:
            if deps["use_container"] and deps["container_path"]:
                run_multiqc_with_container(
                    output_dir, report_dir, report_generator, logo_path, deps, results
                )
            elif deps["multiqc_available"]:
                run_multiqc_native(
                    json_file, report_dir, report_generator, logo_path, results
                )
            else:
                print(
                    "Cannot run MultiQC: missing dependencies and Singularity container not available"
                )
                print(
                    "Please install MultiQC or use a Singularity container with MultiQC installed"
                )
        else:
            # Just generate config without running MultiQC
            generate_multiqc_config_only(
                output_dir, report_dir, report_generator, deps, results
            )

    except Exception as e:
        print(f"Error generating MultiQC report: {str(e)}")
        results["error"] = f"Error generating report: {str(e)}"


def merge_metadata(all_metadata: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge metadata from multiple sequences into a single comprehensive metadata object.

    This ensures the report includes information from all processed sequences.
    """
    if not all_metadata:
        return {}

    # Start with the first sequence's metadata as the base
    merged = all_metadata[0].copy()

    # For multiple sequences, combine gene information
    if len(all_metadata) > 1:
        for metadata in all_metadata[1:]:
            # Combine genes from all sequences
            for gene_name, gene_info in metadata.get("genes", {}).items():
                merged["genes"][gene_name] = gene_info

            # Combine validation results
            merged["validation"].extend(metadata.get("validation", []))

    return merged


def run_multiqc_with_container(
    output_dir: str,
    report_dir: str,
    report_generator: Any,
    logo_path: Optional[str],
    deps: Dict[str, Any],
    results: Dict[str, Any],
) -> None:
    """Run MultiQC using Singularity container."""
    print(f"Using Singularity container for MultiQC: {deps['container_path']}")

    # Get absolute paths for container binding
    output_dir_abs = os.path.abspath(output_dir)

    # Create a temporary directory for container operation
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Copy visualization files to temp directory
            for file_path in results["files_generated"]:
                rel_path = os.path.relpath(file_path, output_dir_abs)
                temp_file_path = os.path.join(temp_dir, rel_path)
                os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
                shutil.copy2(file_path, temp_file_path)

            # Generate config in the temp directory
            config_file = report_generator.generate_config()
            temp_config = os.path.join(temp_dir, os.path.basename(config_file))
            shutil.copy2(config_file, temp_config)
            results["config_file"] = config_file

            # Use shell -c to run commands inside container
            shell_command = f"cd {temp_dir} && multiqc . -o multiqc_report --config {os.path.basename(temp_config)}"
            container_cmd = [
                "singularity",
                "exec",
                "--bind",
                temp_dir,
                deps["container_path"],
                "sh",  # Use shell to interpret commands
                "-c",
                shell_command,
            ]

            # Store the command for reference
            results["multiqc_command"] = " ".join(container_cmd)

            # Run the command
            result = subprocess.run(container_cmd, check=True)
            success = result.returncode == 0

            # Copy report back if successful
            # Modify this section in run_multiqc_with_container
            if success and os.path.exists(os.path.join(temp_dir, "multiqc_report")):
                # Create report dir and copy everything
                copy_report_from_temp(temp_dir, report_dir)

                # Check for both possible filenames
                report_found = False
                for filename in [
                    "hyrise_resistance_report.html",
                    "multiqc_report.html",
                ]:
                    if os.path.exists(os.path.join(report_dir, filename)):
                        print(f"Found report file: {filename}")
                        report_found = True
                        # Post-process the report
                        report_generator.post_process_report(logo_path)
                        print(
                            f"MultiQC report generated and customized in {report_dir}"
                        )
                        break

                if not report_found:
                    print(
                        "Error: No HTML report file found after copying from container"
                    )
        except subprocess.CalledProcessError as e:
            print(f"Error in container-based report generation: {e}")
            results["error"] = f"Container execution error: {str(e)}"
        except Exception as e:
            print(f"Error in container-based report generation: {str(e)}")
            results["error"] = f"Container execution error: {str(e)}"


def copy_report_from_temp(temp_dir: str, report_dir: str) -> None:
    """Copy MultiQC report from temporary directory to final location."""
    os.makedirs(report_dir, exist_ok=True)
    for root, dirs, files in os.walk(os.path.join(temp_dir, "multiqc_report")):
        for dir_name in dirs:
            os.makedirs(os.path.join(report_dir, dir_name), exist_ok=True)
        for file_name in files:
            src_file = os.path.join(root, file_name)
            rel_path = os.path.relpath(
                src_file, os.path.join(temp_dir, "multiqc_report")
            )
            dest_file = os.path.join(report_dir, rel_path)
            shutil.copy2(src_file, dest_file)


def run_multiqc_native(
    json_file: str,
    report_dir: str,
    report_generator: Any,
    logo_path: Optional[str],
    results: Dict[str, Any],
) -> None:
    """Run MultiQC using native installation."""
    try:
        # Generate the report using the report generator class
        report_results = report_generator.generate_report(
            input_data_path=json_file,
            logo_path=logo_path,
            run_multiqc=True,
            skip_html_mod=False,
        )

        # Update results with information from report generation
        results["config_file"] = report_generator.config_path

        if report_results["report_path"]:
            print(f"MultiQC report generated in {report_dir}")
        else:
            print("Error generating MultiQC report. Check the logs for details.")
            if report_results["errors"]:
                for error in report_results["errors"]:
                    print(f"  - {error}")

    except Exception as e:
        print(f"Error running MultiQC: {str(e)}")
        results["error"] = f"Native MultiQC error: {str(e)}"


def generate_multiqc_config_only(
    output_dir: str,
    report_dir: str,
    report_generator: Any,
    deps: Dict[str, Any],
    results: Dict[str, Any],
) -> None:
    """Generate MultiQC config file without running MultiQC."""
    # Generate the config file
    config_file = report_generator.generate_config()
    results["config_file"] = config_file
    print(f"MultiQC config file created at {config_file}")

    # Provide command information
    if deps["multiqc_available"]:
        cmd = f"multiqc {output_dir} -o {report_dir} --config {config_file}"
        results["multiqc_command"] = cmd
        print("You can generate the report by running the following command:")
        print(cmd)
    elif deps["use_container"] and deps["container_path"]:
        output_dir_abs = os.path.abspath(output_dir)
        cmd = f"singularity exec --bind {output_dir_abs} {deps['container_path']} sh -c 'cd {output_dir_abs} && multiqc . -o multiqc_report --config {os.path.basename(config_file)}'"
        results["multiqc_command"] = cmd
        print("You can generate the report using the container with:")
        print(cmd)
    else:
        print("MultiQC is not available locally and Singularity container not found.")
        print("Please install MultiQC to generate the report.")


def print_processing_summary(results: Dict[str, Any]) -> None:
    """Print a summary of the processing results."""
    processed = len(results["processed_sequences"])
    skipped = len(results["skipped_sequences"])

    print(f"\nProcessing Summary:")
    print(
        f"Processed {processed} sequence(s): {', '.join(results['processed_sequences'])}"
    )

    if skipped > 0:
        print(
            f"Skipped {skipped} sequence(s): {', '.join(results['skipped_sequences'])}"
        )

    print(f"Generated {len(results['files_generated'])} visualization files")

    if results.get("report_dir"):
        print(f"Report directory: {results['report_dir']}")

    print(f"MultiQC custom content files created in {results['output_dir']}")


def handle_error(
    error_message: str, results: Dict[str, Any], include_traceback: bool = False
) -> None:
    """Handle errors by updating results dictionary and logging error details."""
    print(error_message)
    if include_traceback:
        print(traceback.format_exc())

    results["success"] = False
    results["error"] = error_message

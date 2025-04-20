# hyrise/core/processor.py
"""
Main processing logic for HyRISE package
"""
import os
import subprocess
import tempfile
import shutil
from datetime import datetime

from hyrise.core.file_utils import extract_sample_id, load_json_file
from hyrise.core.report_config import generate_multiqc_config, generate_multiqc_command
from hyrise.utils.container_utils import ensure_dependencies, run_with_singularity
from hyrise.visualizers.resistance import (
    create_resistance_table,
    create_relevant_drug_commentary,
    create_resistance_level_distribution,
    create_partial_score_analysis,
)
from hyrise.visualizers.mutations import (
    create_mutation_table,
    create_mutation_position_map,
)
from hyrise.visualizers.metadata import create_version_information
from hyrise.visualizers.interpretation import create_interpretation_guide


def process_files(
    json_file,
    output_dir,
    sample_name=None,
    generate_report=False,
    run_multiqc=False,
    use_container=None,
):
    """
    Process Sierra JSON file to create MultiQC visualizations

    Args:
        json_file (str): Path to the Sierra JSON file
        output_dir (str): Directory where output files will be created
        sample_name (str, optional): Sample name to use in the report.
            If not provided, it will be extracted from the filename.
        generate_report (bool): Whether to generate a MultiQC config file
        run_multiqc (bool): Whether to run MultiQC to generate the report
        use_container (bool, optional): Whether to use Singularity container.
            If None, auto-detect based on dependencies. If True, force container.
            If False, force native execution.

    Returns:
        dict: Summary of the processing results including paths to the generated files
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Get absolute paths for container binding
    json_file_abs = os.path.abspath(json_file)
    output_dir_abs = os.path.abspath(output_dir)

    # Initialize results
    results = {
        "json_file": json_file_abs,
        "output_dir": output_dir_abs,
        "files_generated": [],
        "config_file": None,
        "report_dir": None,
        "multiqc_command": None,
        "container_used": False,
    }

    # Check dependencies and container availability
    deps = ensure_dependencies(use_container)
    results.update({"dependencies": deps, "container_used": deps["use_container"]})

    try:
        # Handle JSON processing
        # This part is always done natively because it's pure Python
        data = load_json_file(json_file)

        # Get sample name - use provided name or extract from filename
        if not sample_name:
            sample_name = extract_sample_id(json_file)

        results["sample_name"] = sample_name

        # Get formatted date for the report
        formatted_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Process drug resistance data
        if "drugResistance" in data:
            create_resistance_table(data, sample_name, output_dir)
            create_relevant_drug_commentary(data, sample_name, output_dir)
            create_resistance_level_distribution(data, sample_name, output_dir)
            create_partial_score_analysis(data, sample_name, output_dir)
            create_version_information(data, sample_name, formatted_date, output_dir)

        # Process mutation data
        if "alignedGeneSequences" in data:
            create_mutation_table(data, sample_name, output_dir)
            create_mutation_position_map(data, sample_name, output_dir)

        # Create interpretation guide
        create_interpretation_guide(output_dir)

        # Get list of generated files
        for root, _, files in os.walk(output_dir):
            for file in files:
                if file.endswith("_mqc.json") or file.endswith("_mqc.html"):
                    results["files_generated"].append(os.path.join(root, file))

        # Generate MultiQC config if requested
        if generate_report:
            config_file = generate_multiqc_config(output_dir, sample_name)
            results["config_file"] = config_file

            # Generate the MultiQC command
            report_dir = os.path.join(output_dir, "multiqc_report")
            results["report_dir"] = report_dir

            # If we're running MultiQC and container is needed
            if run_multiqc:
                if deps["use_container"] and deps["container_path"]:
                    try:
                        print(
                            f"Using Singularity container for MultiQC: {deps['container_path']}"
                        )

                        # Create a temporary directory for the MultiQC operation
                        with tempfile.TemporaryDirectory() as temp_dir:
                            # Copy all necessary files to temp directory
                            for file_path in results["files_generated"]:
                                rel_path = os.path.relpath(file_path, output_dir_abs)
                                temp_file_path = os.path.join(temp_dir, rel_path)

                                # Create any necessary subdirectories
                                os.makedirs(
                                    os.path.dirname(temp_file_path), exist_ok=True
                                )

                                # Copy the file
                                shutil.copy2(file_path, temp_file_path)

                            # Copy the config file
                            temp_config = os.path.join(
                                temp_dir, os.path.basename(config_file)
                            )
                            shutil.copy2(config_file, temp_config)

                            # Create output directory in temp dir
                            temp_report_dir = os.path.join(temp_dir, "multiqc_report")
                            os.makedirs(temp_report_dir, exist_ok=True)

                            # Build command for inside the container
                            # Use shell command to ensure we can change directory
                            container_cmd = [
                                "singularity",
                                "exec",
                                "--bind",
                                temp_dir,
                                deps["container_path"],
                                "sh",
                                "-c",
                                f"cd {temp_dir} && multiqc . -o multiqc_report --config {os.path.basename(temp_config)}",
                            ]

                            # Run the command
                            subprocess.run(container_cmd, check=True)

                            # If successful, copy the report back to the original directory
                            if os.path.exists(temp_report_dir):
                                # Create the report directory in the output dir if it doesn't exist
                                os.makedirs(report_dir, exist_ok=True)

                                # Copy all report files
                                for root, dirs, files in os.walk(temp_report_dir):
                                    for dir_name in dirs:
                                        os.makedirs(
                                            os.path.join(report_dir, dir_name),
                                            exist_ok=True,
                                        )

                                    for file_name in files:
                                        src_file = os.path.join(root, file_name)
                                        rel_path = os.path.relpath(
                                            src_file, temp_report_dir
                                        )
                                        dest_file = os.path.join(report_dir, rel_path)
                                        shutil.copy2(src_file, dest_file)

                        print(f"MultiQC report generated in {report_dir}")
                        results["multiqc_command"] = (
                            f"singularity exec --bind {output_dir_abs} {deps['container_path']} sh -c 'cd {output_dir_abs} && multiqc . -o multiqc_report --config {os.path.basename(config_file)}'"
                        )

                    except Exception as e:
                        print(f"Error running MultiQC with container: {str(e)}")
                        print(
                            "Missing dependencies: "
                            + ", ".join(deps["missing_dependencies"])
                        )
                        print(
                            "Please install the missing dependencies or ensure the Singularity container is available."
                        )

                # Use local MultiQC if available
                elif deps["multiqc_available"]:
                    multiqc_command = generate_multiqc_command(
                        config_file, output_dir, report_dir
                    )
                    results["multiqc_command"] = multiqc_command

                    try:
                        subprocess.run(multiqc_command, shell=True, check=True)
                        print(f"MultiQC report generated in {report_dir}")
                    except subprocess.CalledProcessError as e:
                        print(f"Error running MultiQC: {str(e)}")
                        print(
                            "You can run MultiQC manually with the following command:"
                        )
                        print(multiqc_command)

                # Cannot run MultiQC - dependencies missing and no container
                else:
                    print(
                        "Cannot run MultiQC: missing dependencies and Singularity container not available"
                    )
                    print(
                        "Please install MultiQC or use a Singularity container with MultiQC installed"
                    )

            # Just generate the config, not running MultiQC
            else:
                print(f"MultiQC config file created at {config_file}")

                if deps["multiqc_available"]:
                    # Generate standard command
                    multiqc_command = generate_multiqc_command(
                        config_file, output_dir, report_dir
                    )
                    results["multiqc_command"] = multiqc_command
                    print(
                        "You can generate the report by running the following command:"
                    )
                    print(multiqc_command)
                elif deps["use_container"] and deps["container_path"]:
                    # Generate container command
                    container_cmd = f"singularity exec --bind {output_dir_abs} {deps['container_path']} sh -c 'cd {output_dir_abs} && multiqc . -o multiqc_report --config {os.path.basename(config_file)}'"
                    results["multiqc_command"] = container_cmd
                    print("You can generate the report using the container with:")
                    print(results["multiqc_command"])
                else:
                    print(
                        "MultiQC is not available locally and Singularity container not found."
                    )
                    print("Please install MultiQC to generate the report.")

        print(f"MultiQC custom content files created in {output_dir}")

        return results

    except Exception as e:
        print(f"Error processing file {json_file}: {str(e)}")
        raise

# hyrise/core/processor.py
"""
Main processing logic for HyRISE package
"""
import os
import tempfile
import shutil
import subprocess
from datetime import datetime

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
    json_file,
    output_dir,
    sample_name=None,
    generate_report=False,
    run_multiqc=False,
    guide=False,
    sample_info=False,
    contact_email=None,
    logo_path=None,
    use_container=None,
    container_path=None,
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
        guide (bool): Whether to include interpretation guides
        sample_info (bool): Whether to include sample information
        contact_email (str, optional): Contact email to include in the report
        logo_path (str, optional): Path to custom logo file
        use_container (bool, optional): Whether to use Singularity container.
            If None, auto-detect based on dependencies. If True, force container.
            If False, force native execution.
        container_path (str, optional): Path to the Singularity container

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

    # Override container path if specified
    if container_path and os.path.exists(container_path):
        deps["container_path"] = container_path

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

        # Generate all the standard visualizations
        create_drug_resistance_profile(data, sample_name, output_dir)
        create_drug_class_resistance_summary(data, sample_name, output_dir)

        # Generate mutation-resistance impact visualizations
        create_mutation_resistance_contribution(data, sample_name, output_dir)
        create_mutation_clinical_commentary(data, sample_name, output_dir)
        create_mutation_details_table(data, sample_name, output_dir)
        create_mutation_position_visualization(data, sample_name, output_dir)
        create_mutation_type_summary(data, sample_name, output_dir)

        # Generate metadata information
        if guide:
            create_unified_report_section(data, sample_name, formatted_date, output_dir)

        # Process sample information
        if sample_info:
            create_sample_analysis_info(data, sample_name, formatted_date, output_dir)

        # Get list of generated files
        for root, _, files in os.walk(output_dir):
            for file in files:
                if file.endswith("_mqc.json") or file.endswith("_mqc.html"):
                    results["files_generated"].append(os.path.join(root, file))

        # Generate MultiQC report if requested
        if generate_report:
            # Initialize our report generator class
            report_generator = HyRISEReportGenerator(
                output_dir=output_dir,
                version=__version__,
                sample_name=sample_name,
                contact_email=contact_email,
            )

            # Extract metadata from the Sierra JSON data
            metadata_info = report_generator.create_metadata_summary(data)
            report_generator.metadata_info = metadata_info
            print(f"Metadata summary created: {metadata_info}")

            # Store these for use in the results
            report_dir = os.path.join(output_dir, "multiqc_report")
            results["report_dir"] = report_dir

            if run_multiqc:
                # Generate report and handle different execution modes
                if deps["use_container"] and deps["container_path"]:
                    print(
                        f"Using Singularity container for MultiQC: {deps['container_path']}"
                    )

                    # Create a temporary directory for container operation
                    with tempfile.TemporaryDirectory() as temp_dir:
                        # Copy visualization files to temp directory
                        for file_path in results["files_generated"]:
                            rel_path = os.path.relpath(file_path, output_dir_abs)
                            temp_file_path = os.path.join(temp_dir, rel_path)
                            os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
                            shutil.copy2(file_path, temp_file_path)

                        try:
                            # Generate config in the temp directory
                            config_file = report_generator.generate_config()
                            temp_config = os.path.join(
                                temp_dir, os.path.basename(config_file)
                            )
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
                            if success and os.path.exists(
                                os.path.join(temp_dir, "multiqc_report")
                            ):
                                # Create report dir and copy everything
                                os.makedirs(report_dir, exist_ok=True)
                                for root, dirs, files in os.walk(
                                    os.path.join(temp_dir, "multiqc_report")
                                ):
                                    for dir_name in dirs:
                                        os.makedirs(
                                            os.path.join(report_dir, dir_name),
                                            exist_ok=True,
                                        )
                                    for file_name in files:
                                        src_file = os.path.join(root, file_name)
                                        rel_path = os.path.relpath(
                                            src_file,
                                            os.path.join(temp_dir, "multiqc_report"),
                                        )
                                        dest_file = os.path.join(report_dir, rel_path)
                                        shutil.copy2(src_file, dest_file)

                                # Modify HTML if report was generated
                                if os.path.exists(
                                    os.path.join(report_dir, "multiqc_report.html")
                                ):
                                    report_generator.post_process_report(logo_path)
                                    print(
                                        f"MultiQC report generated and customized in {report_dir}"
                                    )
                            else:
                                print(f"Error running MultiQC via container")

                        except subprocess.CalledProcessError as e:
                            print(f"Error in container-based report generation: {e}")
                        except Exception as e:
                            print(
                                f"Error in container-based report generation: {str(e)}"
                            )

                # Use native MultiQC if available
                elif deps["multiqc_available"]:
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
                            print(
                                "Error generating MultiQC report. Check the logs for details."
                            )
                            if report_results["errors"]:
                                for error in report_results["errors"]:
                                    print(f"  - {error}")

                    except Exception as e:
                        print(f"Error running MultiQC: {str(e)}")

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
                # Generate the config file
                config_file = report_generator.generate_config()
                results["config_file"] = config_file
                print(f"MultiQC config file created at {config_file}")

                # Provide command information
                if deps["multiqc_available"]:
                    cmd = f"multiqc {output_dir} -o {report_dir} --config {config_file}"
                    results["multiqc_command"] = cmd
                    print(
                        "You can generate the report by running the following command:"
                    )
                    print(cmd)
                elif deps["use_container"] and deps["container_path"]:
                    cmd = f"singularity exec --bind {output_dir_abs} {deps['container_path']} sh -c 'cd {output_dir_abs} && multiqc . -o multiqc_report --config {os.path.basename(config_file)}'"
                    results["multiqc_command"] = cmd
                    print("You can generate the report using the container with:")
                    print(cmd)
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

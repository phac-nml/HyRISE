# hyrise/visualizers/info_and_guides.py
"""
Sample information and interpretation guides for HyRISE package

This module provides functions for generating comprehensive sample information
and interpretation guides for HIV drug resistance analysis, presented in a
unified section of the MultiQC report.
"""

import os
import json
from collections import defaultdict
from hyrise import __version__
from hyrise.utils.html_utils import (
    create_html_header,
    create_html_footer,
    create_styled_table,
)


def create_sample_analysis_info(data, sample_id, formatted_date, output_dir):
    """
    Create sample analysis information section for MultiQC report

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        formatted_date (str): Formatted date string for the report
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Extract version information
    version_info = {}
    database_date = ""
    database_version = ""

    for dr_entry in data.get("drugResistance", []):
        if "version" in dr_entry:
            gene_name = dr_entry["gene"]["name"]
            version = dr_entry["version"].get("text", "Unknown")
            publish_date = dr_entry["version"].get("publishDate", "Unknown")

            # Capture for report header
            if database_version == "":
                database_version = version
            if database_date == "":
                database_date = publish_date

            if gene_name not in version_info:
                version_info[gene_name] = {}

            version_info[gene_name]["version"] = version
            version_info[gene_name]["publishDate"] = publish_date

    # Extract sequence information
    sequence_info = {
        "subtype": data.get("subtypeText", "Unknown"),
        "genes": [],
        "validation": data.get("validationResults", []),
    }

    # Collect gene information
    for gene_seq in data.get("alignedGeneSequences", []):
        gene_name = gene_seq["gene"]["name"]
        first_aa = gene_seq.get("firstAA", "Unknown")
        last_aa = gene_seq.get("lastAA", "Unknown")
        mutations_count = len(gene_seq.get("mutations", []))
        sdrm_count = len(gene_seq.get("SDRMs", []))

        sequence_info["genes"].append(
            {
                "name": gene_name,
                "first_aa": first_aa,
                "last_aa": last_aa,
                "length": (
                    last_aa - first_aa + 1
                    if isinstance(first_aa, int) and isinstance(last_aa, int)
                    else "Unknown"
                ),
                "mutations_count": mutations_count,
                "sdrm_count": sdrm_count,
            }
        )

    # Create both MultiQC native tables and HTML content
    create_sample_info_table(
        data,
        sample_id,
        formatted_date,
        version_info,
        database_version,
        database_date,
        sequence_info,
        output_dir,
    )
    create_gene_info_table(data, sample_id, sequence_info, output_dir)

    # Create HTML content with validation messages that are harder to show in tables
    if sequence_info["validation"]:
        html_content = create_html_header(
            "sequence_validation",
            "Sequence Validation Results",
            "Validation results and potential issues with the sequence data.",
        )

        html_content += "<h3>Sequence Validation</h3>\n"
        html_content += "<div class='alert alert-info'>\n"
        html_content += "<ul>\n"

        for validation in sequence_info["validation"]:
            level = validation.get("level", "")
            message = validation.get("message", "")

            alert_class = "info"
            if level == "WARNING":
                alert_class = "warning"
            elif level == "SEVERE WARNING":
                alert_class = "warning"
            elif level == "CRITICAL":
                alert_class = "danger"

            html_content += f"<li class='text-{alert_class}'><strong>{level}:</strong> {message}</li>\n"

        html_content += "</ul>\n"
        html_content += "</div>\n"
        html_content += create_html_footer()

        # Write to file
        output_file = os.path.join(output_dir, "sequence_validation_mqc.html")
        with open(output_file, "w") as f:
            f.write(html_content)


def create_interpretation_guides(output_dir):
    """
    Create interpretation guides for resistance scores and mutation types
    using MultiQC native tables

    Args:
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Create tables for interpretation guides
    create_resistance_interpretation_table(output_dir)
    create_mutation_type_table(output_dir)
    create_drug_class_info_table(output_dir)


def create_sample_info_table(
    data,
    sample_id,
    formatted_date,
    version_info,
    database_version,
    database_date,
    sequence_info,
    output_dir,
):
    """
    Create a MultiQC native table with sample information

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        formatted_date (str): Formatted date string for the report
        version_info (dict): Version information for each gene
        database_version (str): HIV drug resistance database version
        database_date (str): HIV drug resistance database date
        sequence_info (dict): Information about the sequence
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Create table data
    table_data = {
        sample_id: {
            "Sample ID": sample_id,
            "Analysis Date": formatted_date,
            # "HIV Subtype": sequence_info["subtype"],
            "Database Version": database_version,
            "Database Date": database_date,
            "HyRISE Version": __version__,
        }
    }

    # Define table headers
    headers = {
        "Sample ID": {
            "title": "Sample ID",
            "description": "Sample identifier",
        },
        "Analysis Date": {
            "title": "Analysis Date",
            "description": "Date of the analysis",
        },
        # "HIV Subtype": {
        #     "title": "HIV Subtype",
        #     "description": "HIV subtype detected in the sample",
        # },
        "Database Version": {
            "title": "Database Version",
            "description": "HIV drug resistance database version used",
        },
        "Database Date": {
            "title": "Database Date",
            "description": "Date of the HIV drug resistance database",
        },
        "HyRISE Version": {
            "title": "HyRISE Version",
            "description": "Version of the HyRISE software used",
        },
    }

    # Define table config
    pconfig = {
        "id": "sample_info_table",
        "title": "Sample Information",
        "namespace": "HyRISE",
        "save_file": True,
        "raw_data_fn": "sample_info_table",
        "sort_rows": False,
        "col1_header": "Sample Name",
    }

    # Create table data as JSON
    table_json = {
        "id": "sample_info_table",
        "section_name": "Sample Information",
        "description": "Basic information about the sample and analysis",
        "plot_type": "table",
        "pconfig": pconfig,
        "data": table_data,
        "headers": headers,
    }

    # Write to file
    output_file = os.path.join(output_dir, "sample_info_table_mqc.json")
    with open(output_file, "w") as f:
        json.dump(table_json, f, indent=2)


def create_gene_info_table(data, sample_id, sequence_info, output_dir):
    """
    Create a MultiQC native table with gene information

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        sequence_info (dict): Information about the sequence
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Create table data for each gene
    table_data = {}

    for gene in sequence_info["genes"]:
        gene_name = gene["name"]
        row_id = f"{sample_id}_{gene_name}"

        table_data[row_id] = {
            "Gene": gene_name,
            "Coverage Start": gene["first_aa"],
            "Coverage End": gene["last_aa"],
            "Length": gene["length"],
            "Mutations": gene["mutations_count"],
            "SDRMs": gene["sdrm_count"],
        }

    # Define table headers
    headers = {
        "Gene": {
            "title": "Gene",
            "description": "HIV gene name",
        },
        "Coverage Start": {
            "title": "Start Position",
            "description": "Start position of the sequence coverage",
        },
        "Coverage End": {
            "title": "End Position",
            "description": "End position of the sequence coverage",
        },
        "Length": {
            "title": "Length",
            "description": "Length of the sequence coverage in amino acids",
        },
        "Mutations": {
            "title": "Mutations",
            "description": "Number of mutations detected",
            "scale": "RdYlGn-rev",
            "min": 0,
        },
        "SDRMs": {
            "title": "SDRMs",
            "description": "Number of Surveillance Drug Resistance Mutations detected",
            "scale": "RdYlGn-rev",
            "min": 0,
        },
    }

    # Define table config
    pconfig = {
        "id": "gene_info_table",
        "title": "Sequence Coverage",
        "namespace": "HyRISE",
        "save_file": True,
        "raw_data_fn": "gene_info_table",
        "sort_rows": False,
        "col1_header": "Gene",
    }

    # Create table data as JSON
    table_json = {
        "id": "gene_info_table",
        "section_name": "Sequence Coverage",
        "description": "Information about the sequence coverage for each gene",
        "plot_type": "table",
        "pconfig": pconfig,
        "data": table_data,
        "headers": headers,
    }

    # Write to file
    output_file = os.path.join(output_dir, "gene_info_table_mqc.json")
    with open(output_file, "w") as f:
        json.dump(table_json, f, indent=2)


def create_resistance_interpretation_table(output_dir):
    """
    Create a MultiQC native table with resistance score interpretations

    Args:
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Define the resistance score interpretations
    score_data = {
        "score_0_9": {
            "Score Range": "0-9",
            "Interpretation": "Susceptible - The virus is expected to be fully susceptible to the drug.",
            "Clinical Implication": "Standard dosing of the drug is likely to be effective.",
        },
        "score_10_14": {
            "Score Range": "10-14",
            "Interpretation": "Potential Low-Level Resistance",
            "Clinical Implication": "The virus may have slightly reduced susceptibility to the drug, but it likely remains clinically effective.",
        },
        "score_15_29": {
            "Score Range": "15-29",
            "Interpretation": "Low-Level Resistance",
            "Clinical Implication": "The virus has low-level resistance that may be overcome with higher drug exposure; consider alternative options if available.",
        },
        "score_30_59": {
            "Score Range": "30-59",
            "Interpretation": "Intermediate Resistance",
            "Clinical Implication": "The virus has intermediate resistance to the drug; reduced virologic response is likely unless drug exposure is increased.",
        },
        "score_60plus": {
            "Score Range": "≥60",
            "Interpretation": "High-Level Resistance",
            "Clinical Implication": "The virus has high-level resistance to the drug; the drug is unlikely to be effective even at increased doses.",
        },
    }

    # Define table headers
    headers = {
        "Score Range": {
            "title": "Score Range",
            "description": "Range of drug resistance scores",
        },
        "Interpretation": {
            "title": "Interpretation",
            "description": "Clinical interpretation of the resistance level",
        },
        "Clinical Implication": {
            "title": "Clinical Implication",
            "description": "Potential impact on treatment decisions",
        },
    }

    # Define table config with color-coding
    pconfig = {
        "id": "resistance_interpretation_table",
        "title": "Resistance Score Interpretation",
        "namespace": "HyRISE",
        "save_file": True,
        "raw_data_fn": "resistance_interpretation_table",
        "sort_rows": False,
        "col1_header": "Score Range",
        "bgcols": {
            "Score Range": {
                "0-9": "#d1e7dd",  # Green
                "10-14": "#cff4fc",  # Light blue
                "15-29": "#fff3cd",  # Light yellow
                "30-59": "#f8d7da",  # Light red
                "≥60": "#f8d7da",  # Light red
            }
        },
    }

    # Create table data as JSON
    table_json = {
        "id": "resistance_interpretation_table",
        "section_name": "Resistance Score Interpretation",
        "description": "Guide to interpreting drug resistance scores in this report",
        "plot_type": "table",
        "pconfig": pconfig,
        "data": score_data,
        "headers": headers,
    }

    # Write to file
    output_file = os.path.join(output_dir, "resistance_interpretation_table_mqc.json")
    with open(output_file, "w") as f:
        json.dump(table_json, f, indent=2)


def create_mutation_type_table(output_dir):
    """
    Create a MultiQC native table with mutation type explanations

    Args:
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Define mutation type data
    mutation_data = {
        "major": {
            "Type": "Major",
            "Definition": "Primary mutations that directly cause resistance to one or more antiretroviral drugs.",
            "Impact": "Significant impact on drug susceptibility; can cause resistance by themselves.",
        },
        "accessory": {
            "Type": "Accessory",
            "Definition": "Secondary mutations that enhance resistance when present with major mutations.",
            "Impact": "May compensate for reduced viral fitness or increase resistance levels in combination with major mutations.",
        },
        "sdrm": {
            "Type": "SDRM",
            "Definition": "Surveillance Drug Resistance Mutations - Standard set of mutations used for surveillance.",
            "Impact": "Used in public health surveillance to track transmitted drug resistance in untreated populations.",
        },
        "other": {
            "Type": "Other",
            "Definition": "Mutations with unknown or minimal impact on drug resistance.",
            "Impact": "Usually polymorphisms or mutations that do not significantly affect drug susceptibility.",
        },
    }

    # Define table headers
    headers = {
        "Type": {
            "title": "Mutation Type",
            "description": "Category of mutation",
        },
        "Definition": {
            "title": "Definition",
            "description": "Explanation of the mutation type",
        },
        "Impact": {
            "title": "Clinical Impact",
            "description": "How the mutation affects drug resistance and treatment",
        },
    }

    # Define table config with color-coding
    pconfig = {
        "id": "mutation_type_table",
        "title": "Mutation Type Definitions",
        "namespace": "HyRISE",
        "save_file": True,
        "raw_data_fn": "mutation_type_table",
        "sort_rows": False,
        "col1_header": "Mutation Type",
        "bgcols": {
            "Type": {
                "Major": "#ffdddd",  # Light red
                "Accessory": "#ffffcc",  # Light yellow
                "SDRM": "#d1e7dd",  # Light green
                "Other": "#f8f9fa",  # Light gray
            }
        },
    }

    # Create table data as JSON
    table_json = {
        "id": "mutation_type_table",
        "section_name": "Mutation Type Definitions",
        "description": "Explanations of different mutation types found in HIV drug resistance analysis",
        "plot_type": "table",
        "pconfig": pconfig,
        "data": mutation_data,
        "headers": headers,
    }

    # Write to file
    output_file = os.path.join(output_dir, "mutation_type_table_mqc.json")
    with open(output_file, "w") as f:
        json.dump(table_json, f, indent=2)


def create_drug_class_info_table(output_dir):
    """
    Create a MultiQC native table with drug class information

    Args:
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Define drug class data
    drug_class_data = {
        "nrti": {
            "Drug Class": "NRTIs",
            "Full Name": "Nucleoside/Nucleotide Reverse Transcriptase Inhibitors",
            "Common Resistance Regions": "RT positions 41-219 (TAMs), RT positions 65, 74, 115, 184",
            "Genetic Barrier": "Moderate",
            "Examples": "Tenofovir, Lamivudine, Abacavir, Emtricitabine, Zidovudine",
        },
        "nnrti": {
            "Drug Class": "NNRTIs",
            "Full Name": "Non-Nucleoside Reverse Transcriptase Inhibitors",
            "Common Resistance Regions": "RT positions 100-108, 181, 188, 190, 230",
            "Genetic Barrier": "Low",
            "Examples": "Efavirenz, Nevirapine, Rilpivirine, Doravirine",
        },
        "pi": {
            "Drug Class": "PIs",
            "Full Name": "Protease Inhibitors",
            "Common Resistance Regions": "Protease positions 30, 46, 48, 50, 54, 82, 84, 90",
            "Genetic Barrier": "High",
            "Examples": "Darunavir, Atazanavir, Lopinavir (usually boosted)",
        },
        "insti": {
            "Drug Class": "INSTIs",
            "Full Name": "Integrase Strand Transfer Inhibitors",
            "Common Resistance Regions": "Integrase positions 66, 92, 140, 143, 147, 148, 155",
            "Genetic Barrier": "Variable",
            "Examples": "Dolutegravir, Bictegravir, Raltegravir, Elvitegravir",
        },
    }

    # Define table headers
    headers = {
        "Drug Class": {
            "title": "Drug Class",
            "description": "HIV antiretroviral drug class abbreviation",
        },
        "Full Name": {
            "title": "Full Name",
            "description": "Complete name of the drug class",
        },
        "Common Resistance Regions": {
            "title": "Resistance Regions",
            "description": "Typical gene positions where resistance mutations occur",
        },
        "Genetic Barrier": {
            "title": "Genetic Barrier",
            "description": "Relative number of mutations needed for resistance to develop",
        },
        "Examples": {
            "title": "Example Drugs",
            "description": "Common drugs in this class",
        },
    }

    # Define table config
    pconfig = {
        "id": "drug_class_info_table",
        "title": "HIV Drug Classes",
        "namespace": "HyRISE",
        "save_file": True,
        "raw_data_fn": "drug_class_info_table",
        "sort_rows": False,
        "col1_header": "Drug Class",
    }

    # Create table data as JSON
    table_json = {
        "id": "drug_class_info_table",
        "section_name": "HIV Drug Classes",
        "description": "Information about HIV antiretroviral drug classes and their resistance patterns",
        "plot_type": "table",
        "pconfig": pconfig,
        "data": drug_class_data,
        "headers": headers,
    }

    # Write to file
    output_file = os.path.join(output_dir, "drug_class_info_table_mqc.json")
    with open(output_file, "w") as f:
        json.dump(table_json, f, indent=2)


def create_unified_report_section(data, sample_id, formatted_date, output_dir):
    """
    Create a unified section containing both sample information and interpretation guides

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        formatted_date (str): Formatted date string for the report
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # First, create the individual tables using MultiQC native format
    create_sample_analysis_info(data, sample_id, formatted_date, output_dir)
    create_interpretation_guides(output_dir)

    # Create an HTML section that provides context and links everything together
    html_content = create_html_header(
        "unified_hiv_report_section",
        "HIV Resistance Analysis Guide",
        "Comprehensive view of sample information and HIV drug resistance interpretation.",
    )

    html_content += "<h3>About This Report</h3>\n"
    html_content += """
    <div class="alert alert-info">
        <p>This report provides a comprehensive analysis of HIV drug resistance for the sample. The analysis is based on gene sequence data
        processed through the <strong>HyRISE</strong> (HIV Resistance Interpretation &amp; Scoring Engine) pipeline.</p>
        <p>The report contains the following information:</p>
        <ul>
            <li><strong>Sample Information</strong> - Details about the sample, analysis date, and software versions</li>
            <li><strong>Sequence Coverage</strong> - Information about gene coverage and detected mutations</li>
            <li><strong>Drug Resistance Profiles</strong> - Analysis of resistance to different antiretroviral drugs</li>
            <li><strong>Mutation Analysis</strong> - Details about detected mutations and their impact</li>
            <li><strong>Interpretation Guides</strong> - Guidance on how to interpret resistance scores and mutation types</li>
        </ul>
        <p><strong>How to use this report:</strong> Start by reviewing the executive summary and resistance overview, then explore 
        the detailed analyses of specific drugs and mutations. Use the interpretation guides in this section to understand 
        the meaning of resistance scores and mutation types.</p>
    </div>
    """

    html_content += "<h3>Report Navigation</h3>\n"
    html_content += """
    <div class="card mb-4">
        <div class="card-body">
            <p>This report is organized into the following main sections:</p>
            <div class="row">
                <div class="col-md-6">
                    <div class="card mb-3">
                        <div class="card-header bg-primary text-white">
                            Sample Analysis
                        </div>
                        <div class="card-body">
                            <ul>
                                <li>Sample Information (details about the analysis)</li>
                                <li>Sequence Coverage (gene coverage information)</li>
                                <li>Validation Results (quality assessment)</li>
                            </ul>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card mb-3">
                        <div class="card-header bg-success text-white">
                            Resistance Analysis
                        </div>
                        <div class="card-body">
                            <ul>
                                <li>Executive Summary (high-level overview)</li>
                                <li>Drug Resistance Profiles (by gene)</li>
                                <li>Mutation Details (significant mutations)</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
            <p class="mt-3">Use the navigation menu on the left to jump to specific sections of interest.</p>
        </div>
    </div>
    """

    # Add a note about how to interpret the data
    html_content += "<h3>Understanding HIV Drug Resistance</h3>\n"
    html_content += """
    <p>HIV drug resistance analysis evaluates how mutations in the HIV genome affect the efficacy of antiretroviral drugs.
    The analysis in this report is based on genotypic resistance testing, which identifies mutations known to confer
    resistance to specific drugs.</p>
    <p>Key concepts to understand:</p>
    <ul>
        <li><strong>Resistance Score</strong> - Numerical value that quantifies the level of resistance to a specific drug</li>
        <li><strong>Mutation Types</strong> - Different categories of mutations based on their impact on drug resistance</li>
        <li><strong>Drug Classes</strong> - Groups of antiretroviral drugs with similar mechanisms of action</li>
        <li><strong>SDRMs</strong> - Surveillance Drug Resistance Mutations, a standardized set used to monitor transmitted resistance</li>
    </ul>
    <p>For detailed interpretations of resistance scores and mutation types, refer to the tables in this section.</p>
    """
    html_content += create_html_footer()

    # Write to file
    output_file = os.path.join(output_dir, "unified_report_section_mqc.html")
    with open(output_file, "w") as f:
        f.write(html_content)

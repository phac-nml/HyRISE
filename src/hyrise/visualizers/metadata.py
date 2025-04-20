# hyrise/visualizers/metadata.py
"""
Version and metadata visualizations for HyRISE package
"""
import os
import json
from collections import defaultdict
from ..utils.html_utils import create_html_header, create_html_footer


def create_version_information(data, sample_id, formatted_date, output_dir):
    """
    Create enhanced version information display with sequence details

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        formatted_date (str): Formatted date string for the report
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    version_info = {}
    database_date = ""
    database_version = ""

    # Extract version information
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
        "input_sequence": data.get("inputSequence", {}),
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

    # Create unified version information
    if version_info:
        # Create HTML content
        html_content = create_html_header(
            "version_information",
            "Analysis Information",
            "Comprehensive version and sequence information.",
        )

        html_content += "<h3>HIV Drug Resistance Analysis Information</h3>\n"

        # Add sample metadata
        html_content += "<div class='row'>\n"

        # Left column - basic info
        html_content += "<div class='col-md-6'>\n"
        html_content += "<h4>Sample Information</h4>\n"
        html_content += "<table class='table table-bordered'>\n"
        html_content += "<tr><th>Parameter</th><th>Value</th></tr>\n"
        html_content += f"<tr><td>Sample ID</td><td>{sample_id}</td></tr>\n"
        html_content += f"<tr><td>Analysis Date</td><td>{formatted_date}</td></tr>\n"
        html_content += (
            f"<tr><td>HIV Subtype</td><td>{sequence_info['subtype']}</td></tr>\n"
        )
        html_content += (
            f"<tr><td>Database Version</td><td>{database_version}</td></tr>\n"
        )
        html_content += f"<tr><td>Database Date</td><td>{database_date}</td></tr>\n"
        html_content += "<tr><td>HyRISE Version</td><td>1.0.0</td></tr>\n"
        html_content += "</table>\n"
        html_content += "</div>\n"

        # Right column - sequence info
        html_content += "<div class='col-md-6'>\n"
        html_content += "<h4>Sequence Information</h4>\n"
        html_content += "<table class='table table-bordered'>\n"
        html_content += "<tr><th>Gene</th><th>Coverage</th><th>Length</th><th>Mutations</th><th>SDRMs</th></tr>\n"

        for gene in sequence_info["genes"]:
            html_content += f"<tr>\n"
            html_content += f"  <td>{gene['name']}</td>\n"
            html_content += f"  <td>{gene['first_aa']}-{gene['last_aa']}</td>\n"
            html_content += f"  <td>{gene['length']}</td>\n"
            html_content += f"  <td>{gene['mutations_count']}</td>\n"
            html_content += f"  <td>{gene['sdrm_count']}</td>\n"
            html_content += f"</tr>\n"

        html_content += "</table>\n"
        html_content += "</div>\n"
        html_content += "</div>\n"  # End row

        # Add validation results if any
        if sequence_info["validation"]:
            html_content += "<h4>Sequence Validation</h4>\n"
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

        # Add gene-specific version information if there are multiple genes
        if len(version_info) > 1:
            html_content += "<h4>Gene-Specific Database Versions</h4>\n"
            html_content += "<table class='table table-bordered'>\n"
            html_content += "<tr><th>Gene</th><th>Database Version</th><th>Database Date</th></tr>\n"

            for gene_name, info in sorted(version_info.items()):
                html_content += f"<tr><td>{gene_name}</td><td>{info.get('version', 'Unknown')}</td><td>{info.get('publishDate', 'Unknown')}</td></tr>\n"

            html_content += "</table>\n"

        html_content += create_html_footer()

        # Write to file
        output_file = os.path.join(output_dir, "version_information_mqc.html")
        with open(output_file, "w") as f:
            f.write(html_content)


def create_sample_overview(data, sample_id, output_dir):
    """
    Create an executive summary of the sample's resistance profile

    Args:
        data (dict): The parsed JSON data
        sample_id (str): Sample identifier
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Collect all resistance data
    resistance_by_class = defaultdict(list)
    major_mutations = []

    # Extract resistance levels by drug class
    for dr_entry in data.get("drugResistance", []):
        gene_name = dr_entry["gene"]["name"]

        for drug_score in dr_entry.get("drugScores", []):
            drug_name = drug_score["drug"]["displayAbbr"]
            drug_class = drug_score.get("drugClass", {}).get("name", "Unknown")
            resistance_level = drug_score["text"]
            score = drug_score["score"]
            level = drug_score.get("level", 0)

            resistance_by_class[drug_class].append(
                {
                    "gene": gene_name,
                    "drug": drug_name,
                    "level": level,
                    "level_text": resistance_level,
                    "score": score,
                }
            )

    # Extract major mutations
    for gene_seq in data.get("alignedGeneSequences", []):
        gene_name = gene_seq["gene"]["name"]

        for mutation in gene_seq.get("mutations", []):
            if mutation.get("primaryType") == "Major":
                major_mutations.append(
                    {
                        "gene": gene_name,
                        "text": mutation.get("text", ""),
                        "position": mutation.get("position", ""),
                        "is_sdrm": mutation.get("isSDRM", False),
                    }
                )

    # Create HTML content
    html_content = create_html_header(
        "sample_overview",
        "Executive Summary",
        "High-level overview of resistance findings.",
    )

    html_content += "<h3>Executive Summary</h3>\n"

    # Add CSS for styling
    html_content += """
    <style>
    .summary-card {
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 15px;
        margin-bottom: 20px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    .summary-card h4 {
        margin-top: 0;
        border-bottom: 1px solid #eee;
        padding-bottom: 10px;
        margin-bottom: 15px;
    }
    .resistance-pill {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 15px;
        margin: 3px;
        font-weight: bold;
    }
    .high-resistance {
        background-color: #d9534f;
        color: white;
    }
    .intermediate {
        background-color: #f0ad4e;
        color: white;
    }
    .low-resistance {
        background-color: #5cb85c;
        color: white;
    }
    .potential {
        background-color: #5bc0de;
        color: white;
    }
    .susceptible {
        background-color: #777777;
        color: white;
    }
    .mutation-list {
        list-style-type: none;
        padding-left: 0;
        display: flex;
        flex-wrap: wrap;
    }
    .mutation-item {
        background-color: #f8f9fa;
        border: 1px solid #ddd;
        border-radius: 3px;
        padding: 5px 10px;
        margin: 5px;
        display: inline-block;
    }
    .mutation-item.sdrm {
        border-left: 4px solid #5cb85c;
    }
    </style>
    """

    # Overview Cards
    html_content += "<div class='row'>\n"

    # Left column - Resistance Overview
    html_content += "<div class='col-md-6'>\n"
    html_content += "<div class='summary-card'>\n"
    html_content += "<h4>Resistance Overview</h4>\n"

    for drug_class, drugs in sorted(resistance_by_class.items()):
        html_content += f"<p><strong>{drug_class}:</strong></p>\n"
        html_content += "<div>\n"

        for drug in sorted(drugs, key=lambda x: x["level"], reverse=True):
            css_class = "resistance-pill "
            if drug["level"] == 5:
                css_class += "high-resistance"
            elif drug["level"] == 4:
                css_class += "intermediate"
            elif drug["level"] == 3:
                css_class += "low-resistance"
            elif drug["level"] == 2:
                css_class += "potential"
            else:
                css_class += "susceptible"

            html_content += (
                f"<span class='{css_class}'>{drug['drug']} ({drug['score']})</span>\n"
            )

        html_content += "</div>\n"

    html_content += "</div>\n"  # End summary-card
    html_content += "</div>\n"  # End col

    # Right column - Major Mutations
    html_content += "<div class='col-md-6'>\n"
    html_content += "<div class='summary-card'>\n"
    html_content += "<h4>Major Resistance Mutations</h4>\n"

    if not major_mutations:
        html_content += "<p>No major resistance mutations detected.</p>\n"
    else:
        # Group mutations by gene
        mutations_by_gene = defaultdict(list)
        for mutation in major_mutations:
            mutations_by_gene[mutation["gene"]].append(mutation)

        for gene, mutations in sorted(mutations_by_gene.items()):
            html_content += f"<p><strong>{gene}:</strong></p>\n"
            html_content += "<ul class='mutation-list'>\n"

            for mutation in sorted(mutations, key=lambda x: x["position"]):
                sdrm_class = " sdrm" if mutation["is_sdrm"] else ""
                html_content += (
                    f"<li class='mutation-item{sdrm_class}'>{mutation['text']}</li>\n"
                )

            html_content += "</ul>\n"

    html_content += "</div>\n"  # End summary-card
    html_content += "</div>\n"  # End col

    html_content += "</div>\n"  # End row

    # Generate recommendations (simplified)
    html_content += "<div class='summary-card'>\n"
    html_content += "<h4>Interpretation</h4>\n"

    # Count high and intermediate resistance drugs
    high_count = sum(
        1
        for drugs in resistance_by_class.values()
        for drug in drugs
        if drug["level"] >= 4
    )

    if high_count > 3:
        html_content += "<p class='alert alert-danger'>Significant resistance detected across multiple drug classes. Consider resistance testing and treatment history when selecting a regimen.</p>\n"
    elif high_count > 0:
        html_content += "<p class='alert alert-warning'>Some resistance detected. Consider the resistance profile when selecting antiretroviral drugs.</p>\n"
    else:
        html_content += "<p class='alert alert-success'>No significant resistance detected. Standard regimens may be appropriate.</p>\n"

    html_content += "<p><em>Note: This is a simplified interpretation. Clinical decisions should be made in conjunction with treatment history, medication availability, and other clinical factors.</em></p>\n"

    html_content += "</div>\n"  # End summary-card

    html_content += create_html_footer()

    # Write to file
    output_file = os.path.join(output_dir, "sample_overview_mqc.html")
    with open(output_file, "w") as f:
        f.write(html_content)

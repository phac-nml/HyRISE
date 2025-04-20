"""
Interpretation guides for HyRISE package
"""

import os
from ..utils.html_utils import (
    create_html_header,
    create_html_footer,
    create_styled_table,
)


def create_interpretation_guide(output_dir, detailed=False):
    """
    Create interpretation guides for resistance scores and mutation types

    Args:
        output_dir (str): Directory where output files will be created
        detailed (bool): Whether to include detailed interpretation guides

    Returns:
        None
    """
    # Create basic resistance score interpretation
    create_resistance_interpretation(output_dir)

    # Only create detailed guides if requested
    if detailed:
        create_mutation_definitions(output_dir)
        create_detailed_resistance_concepts(output_dir)


def create_resistance_interpretation(output_dir):
    """
    Create a concise guide for interpreting drug resistance scores

    Args:
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Define the resistance score interpretations
    score_data = [
        [
            "0-9",
            "Susceptible - The virus is expected to be fully susceptible to the drug.",
        ],
        [
            "10-14",
            "Potential Low-Level Resistance - The virus may have slightly reduced susceptibility to the drug.",
        ],
        [
            "15-29",
            "Low-Level Resistance - The virus has low-level resistance to the drug.",
        ],
        [
            "30-59",
            "Intermediate Resistance - The virus has intermediate resistance to the drug.",
        ],
        [
            "≥60",
            "High-Level Resistance - The virus has high-level resistance to the drug.",
        ],
    ]

    # Create HTML content
    html_content = create_html_header(
        "resistance_interpretation_section",
        "Resistance Score Interpretation",
        "This section explains how to interpret the drug resistance scores and levels presented in this report.",
    )

    html_content += "<h3>HIV Drug Resistance Scoring System</h3>\n"
    html_content += create_styled_table(
        headers=["Score Range", "Interpretation"],
        rows=score_data,
        table_class="table table-bordered table-hover",
    )

    html_content += create_html_footer()

    # Write to file
    output_file = os.path.join(output_dir, "resistance_interpretation_mqc.html")
    with open(output_file, "w") as f:
        f.write(html_content)


def create_mutation_definitions(output_dir):
    """
    Create definitions for different mutation types

    Args:
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    # Define the mutation type definitions
    mutation_data = [
        [
            "Major",
            "Primary mutations that directly cause resistance to one or more antiretroviral drugs.",
        ],
        [
            "Accessory",
            "Secondary mutations that enhance resistance when present with major mutations or compensate for reduced viral fitness.",
        ],
        [
            "SDRM",
            "Surveillance Drug Resistance Mutations - Standard set of mutations used for surveillance of transmitted drug resistance.",
        ],
        ["Other", "Mutations with unknown or minimal impact on drug resistance."],
    ]

    # Create HTML content
    html_content = create_html_header(
        "mutation_type_definitions_section",
        "Mutation Type Definitions",
        "This section provides definitions for the different types of mutations identified in the HIV sequence.",
    )

    html_content += "<h3>HIV Resistance Mutation Types</h3>\n"
    html_content += create_styled_table(
        headers=["Mutation Type", "Definition"],
        rows=mutation_data,
        table_class="table table-bordered table-hover",
    )

    html_content += create_html_footer()

    # Write to file
    output_file = os.path.join(output_dir, "mutation_type_definitions_mqc.html")
    with open(output_file, "w") as f:
        f.write(html_content)


def create_detailed_resistance_concepts(output_dir):
    """
    Create detailed guide for HIV resistance concepts

    Args:
        output_dir (str): Directory where output files will be created

    Returns:
        None
    """
    html_content = create_html_header(
        "general_resistance_concepts",
        "HIV Resistance Concepts",
        "General concepts for understanding HIV drug resistance",
    )

    html_content += """
    <h3>Understanding HIV Drug Resistance</h3>
    <h4>Key Concepts</h4>
    <ul>
        <li><strong>Genotypic Resistance</strong>: The presence of mutations in the HIV genome that confer resistance to antiretroviral drugs.</li>
        <li><strong>Phenotypic Resistance</strong>: The reduced susceptibility of the virus to inhibition by antiretroviral drugs in laboratory tests.</li>
        <li><strong>Cross-Resistance</strong>: Resistance to multiple drugs within the same class due to shared resistance pathways.</li>
        <li><strong>Archived Resistance</strong>: Resistant variants that persist in reservoirs and may reemerge under selective pressure.</li>
    </ul>
    <h4>Drug Classes and Resistance Patterns</h4>
    <table class='table table-bordered'>
        <tr>
            <th>Drug Class</th>
            <th>Common Resistance Regions</th>
            <th>Genetic Barrier</th>
        </tr>
        <tr>
            <td>NRTIs</td>
            <td>RT positions 41-219 (TAMs)<br>RT positions 65, 74, 115, 184</td>
            <td>Moderate</td>
        </tr>
        <tr>
            <td>NNRTIs</td>
            <td>RT positions 100-108, 181, 188, 190, 230</td>
            <td>Low</td>
        </tr>
        <tr>
            <td>PIs</td>
            <td>Protease positions 30, 46, 48, 50, 54, 82, 84, 90</td>
            <td>High</td>
        </tr>
        <tr>
            <td>INSTIs</td>
            <td>Integrase positions 66, 92, 140, 143, 147, 148, 155</td>
            <td>Variable</td>
        </tr>
    </table>
    """

    html_content += create_html_footer()

    # Write to file
    output_file = os.path.join(output_dir, "general_resistance_concepts_mqc.html")
    with open(output_file, "w") as f:
        f.write(html_content)

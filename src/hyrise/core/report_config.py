"""
Enhanced HyRISE MultiQC Report Generator with robust HTML modifications
and integrated command-line interface.
"""

import os
import sys
import shutil
import argparse
import subprocess
import yaml
import base64
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional, Union
from bs4 import BeautifulSoup


class HyRISEReportGenerator:
    """Class to handle the generation and customization of MultiQC reports for HyRISE."""

    def __init__(
        self,
        output_dir: str,
        version: str = "0.1.0",
        sample_name: Optional[str] = None,
        metadata_info: Optional[Dict[str, Any]] = None,
        contact_email: Optional[str] = None,
    ):
        """
        Initialize the report generator.

        Args:
            output_dir: Directory where the report will be created
            version: HyRISE version string
            sample_name: Sample name to include in the report
            metadata_info: Metadata information extracted from Sierra JSON
            contact_email: Contact email to include in the report
        """
        self.output_dir = os.path.abspath(output_dir)
        self.version = version
        self.sample_name = sample_name
        self.metadata_info = metadata_info or {}
        self.contact_email = contact_email
        self.report_dir = os.path.join(output_dir, "multiqc_report")
        self.config_path = None
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """Set up a basic logger."""
        import logging

        logger = logging.getLogger("hyrise-report")
        logger.setLevel(logging.INFO)

        # Create console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        ch.setFormatter(formatter)

        # Add the handler to the logger
        logger.addHandler(ch)

        return logger

    def embed_logo(self, logo_path: Optional[str] = None) -> str:
        """
        Encode a logo file as base64 for embedding in HTML.

        Args:
            logo_path: Path to logo file (PNG or SVG)

        Returns:
            str: Data URI for the logo
        """
        # Resolve image path
        if logo_path:
            resolved_path = Path(logo_path)
        else:
            # Look in multiple locations for a default logo
            possible_paths = [
                Path(__file__).parent / "assets" / "hyrise_logo.svg",
                Path(__file__).parent / "assets" / "hyrise_logo.png",
                Path(os.path.dirname(os.path.abspath(__file__)))
                / "assets"
                / "hyrise_logo.svg",
                Path(os.path.dirname(os.path.abspath(__file__)))
                / "assets"
                / "hyrise_logo.png",
            ]

            resolved_path = next((p for p in possible_paths if p.exists()), None)

        self.logger.info(f"Looking for logo at: {resolved_path}")

        # Validate file exists
        if not resolved_path or not resolved_path.exists():
            self.logger.warning(
                f"Logo file not found at {resolved_path}, using fallback"
            )
            # Return an empty string if no logo is found
            return ""

        # Log file details
        self.logger.info(
            f"Found logo file: {resolved_path} ({resolved_path.stat().st_size} bytes)"
        )

        # Validate file extension
        if resolved_path.suffix.lower() not in [".svg", ".png", ".jpg", ".jpeg"]:
            self.logger.warning(
                f"Unsupported file format: {resolved_path.suffix}. Only .svg, .png, .jpg, .jpeg files are supported."
            )
            return ""

        try:
            # Encode image as base64
            with open(resolved_path, "rb") as image_file:
                file_content = image_file.read()
                self.logger.info(f"Read {len(file_content)} bytes from logo file")
                encoded_string = base64.b64encode(file_content).decode("utf-8")

            # Create data URI for embedding
            if resolved_path.suffix.lower() == ".svg":
                mime_type = "image/svg+xml"
            elif resolved_path.suffix.lower() in [".jpg", ".jpeg"]:
                mime_type = "image/jpeg"
            else:
                mime_type = "image/png"

            data_uri = f"data:{mime_type};base64,{encoded_string}"
            self.logger.info(f"Created data URI with length {len(data_uri)}")
            return data_uri
        except Exception as e:
            self.logger.error(f"Error embedding logo: {str(e)}")
            import traceback

            self.logger.error(traceback.format_exc())
            return ""

    def create_metadata_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metadata from Sierra JSON for use in the report.

        Args:
            data: Sierra JSON data

        Returns:
            Dict containing structured metadata
        """
        # Extract database version information
        db_version = None
        db_publish_date = None
        gene_versions: Dict[str, Dict[str, str]] = {}

        for dr in data.get("drugResistance", []):
            gene_name = dr["gene"]["name"]
            version = dr["version"].get("text", "Unknown")
            publish_date = dr["version"].get("publishDate", "Unknown")

            # Capture first seen version as the sample-level reference
            db_version = db_version or version
            db_publish_date = db_publish_date or publish_date

            gene_versions[gene_name] = {
                "version": version,
                "publish_date": publish_date,
            }

        # Extract sequence information
        genes: Dict[str, Dict[str, Any]] = {}

        for gene_seq in data.get("alignedGeneSequences", []):
            gene_name = gene_seq["gene"]["name"]
            first_aa = gene_seq.get("firstAA", 0)
            last_aa = gene_seq.get("lastAA", 0)
            length = (last_aa - first_aa + 1) if first_aa and last_aa else 0

            genes[gene_name] = {
                **gene_versions.get(gene_name, {}),
                "first_aa": first_aa,
                "last_aa": last_aa,
                "length": length,
                "mutations_count": len(gene_seq.get("mutations", [])),
                "sdrm_count": len(gene_seq.get("SDRMs", [])),
            }

        # Create summary structure
        return {
            "sample_id": self.sample_name,
            "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "subtype": data.get("subtypeText", "Unknown"),
            "database": {
                "version": db_version or "Unknown",
                "publish_date": db_publish_date or "Unknown",
            },
            "genes": genes,
            "validation": data.get("validationResults", []),
        }

    def generate_config(self, use_custom_template=False) -> str:
        """
        Generate the MultiQC configuration file.

        Args:
            use_custom_template: Whether to use a custom MultiQC template

        Returns:
            str: Path to the generated config file
        """
        # Debug logging to check if metadata is available
        if self.metadata_info:
            self.logger.info(
                f"Using extracted metadata: {self.metadata_info.get('sample_id', 'Unknown')} with {len(self.metadata_info.get('genes', {}))} genes"
            )
        else:
            self.logger.warning(
                "No metadata information available. Using default values."
            )

        # Ensure we have metadata info available - if not, use default values
        if not self.metadata_info:
            self.logger.warning(
                "No metadata information available. Using default values."
            )
            metadata_info = {
                "sample_id": self.sample_name or "HIV Sample",
                "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "subtype": "Unknown",
                "database": {
                    "version": "Unknown",
                    "publish_date": "Unknown",
                },
                "genes": {},
                "validation": [],
            }
        else:
            metadata_info = self.metadata_info

        # Prepare metadata for report header
        sample_name = metadata_info.get("sample_id") or self.sample_name or "HIV Sample"
        analysis_date = metadata_info.get("analysis_date") or datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        db_info = metadata_info.get("database", {})
        database_version = db_info.get("version", "Unknown")
        database_date = db_info.get("publish_date", "Unknown")

        genes_present = sorted(metadata_info.get("genes", {}).keys())
        genes_analyzed = ", ".join(genes_present) if genes_present else "None"

        # Build the header info
        header = [
            {"Sample Name": sample_name},
            {"Analysis Date": analysis_date},
            {"Genes Analyzed": genes_analyzed},
            {"Stanford DB Version": database_version},
            {"Stanford DB Date": database_date},
        ]

        # Add per-gene mutation/SDRM count lines
        for g in genes_present:
            info = metadata_info["genes"][g]
            header.append(
                {f"{g} Mut / SDRM": f"{info['mutations_count']} / {info['sdrm_count']}"}
            )

        # Always add HyRISE version
        header.append({"HyRISE Version": self.version})

        # Only add email if provided
        if self.contact_email:
            header.append(
                {
                    "Contact E-mail": f"<a href='mailto:{self.contact_email}'>{self.contact_email}</a>"
                }
            )

        # Create the configuration dictionary
        config = {
            # Report title and subtitle
            "title": "HyRISE: Resistance Interpretation & Scoring Engine",
            "subtitle": "HIV Drug Resistance Sequencing Analysis Report",
            "report_comment": "A comprehensive analysis of HIV drug resistance mutations based on sequencing data. "
            "This report leverages Sierra-Local with HyRISE visualization and provides detailed insights "
            "into drug resistance patterns, mutation profiles, and treatment implications.",
            # Built-in MultiQC customization options
            "show_analysis_paths": False,
            "show_analysis_time": True,
            "skip_generalstats": True,
            # Use built-in multiQC features for branding
            # These are more robust than post-processing HTML
            "custom_logo_url": "https://pypi.org/project/hyrise/",
            "custom_logo_title": "HyRISE - HIV Resistance Interpretation & Scoring Engine",
            "introduction": "This report was generated by HyRISE, the HIV Resistance Interpretation & Scoring Engine.",
            # Report header info
            "report_header_info": header,
            "report_section_order": {
                # ===== PROTEASE (PR) SECTIONS =====
                "drug_class_overview_pr_table": {
                    "order": 4000,
                    "section_name": "PR Gene: Overview",
                },
                "drug_resistance_pr_table": {
                    "order": 3900,
                    "section_name": "PR Gene: Resistance Profile",
                    "after": "drug_class_overview_pr_table",
                },
                "mutation_clinical_pr_table": {"after": "drug_resistance_pr_table"},
                "mutation_summary_pr_table": {"after": "mutation_clinical_pr_table"},
                "mutation_details_pr_table": {"after": "mutation_summary_pr_table"},
                "mutation_contribution_pr_table": {
                    "after": "mutation_details_pr_table"
                },
                "mutation_position_map_pr": {"after": "mutation_contribution_pr_table"},
                # ===== REVERSE TRANSCRIPTASE (RT) SECTIONS =====
                "drug_class_overview_rt_table": {
                    "order": 3800,
                    "section_name": "RT Gene: Overview",
                },
                "drug_resistance_rt_table": {
                    "order": 3700,
                    "section_name": "RT Gene: Resistance Profile",
                    "after": "drug_class_overview_rt_table",
                },
                "mutation_clinical_rt_table": {"after": "drug_resistance_rt_table"},
                "mutation_summary_rt_table": {"after": "mutation_clinical_rt_table"},
                "mutation_details_rt_table": {"after": "mutation_summary_rt_table"},
                "mutation_contribution_rt_table": {
                    "after": "mutation_details_rt_table"
                },
                "mutation_position_map_rt": {"after": "mutation_contribution_rt_table"},
                # ===== INTEGRASE (IN) SECTIONS =====
                # These follow the same pattern as PR and RT
                "drug_class_overview_in_table": {
                    "order": 3600,
                    "section_name": "IN Gene: Overview",
                },
                "drug_resistance_in_table": {
                    "order": 3500,
                    "section_name": "IN Gene: Resistance Profile",
                    "after": "drug_class_overview_in_table",
                },
                "mutation_clinical_in_table": {"after": "drug_resistance_in_table"},
                "mutation_summary_in_table": {"after": "mutation_clinical_in_table"},
                "mutation_details_in_table": {"after": "mutation_summary_in_table"},
                "mutation_contribution_in_table": {
                    "after": "mutation_details_in_table"
                },
                "mutation_position_map_in": {"after": "mutation_contribution_in_table"},
                # ===== CAPSID (CA) SECTIONS (For future use) =====
                "drug_class_overview_ca_table": {
                    "order": 3400,
                    "section_name": "CA Gene: Overview",
                },
                "drug_resistance_ca_table": {
                    "order": 3300,
                    "section_name": "CA Gene: Resistance Profile",
                    "after": "drug_class_overview_ca_table",
                },
                "mutation_clinical_ca_table": {"after": "drug_resistance_ca_table"},
                "mutation_summary_ca_table": {"after": "mutation_clinical_ca_table"},
                "mutation_details_ca_table": {"after": "mutation_summary_ca_table"},
                "mutation_contribution_ca_table": {
                    "after": "mutation_details_ca_table"
                },
                "mutation_position_map_ca": {"after": "mutation_contribution_ca_table"},
                # ===== INTERPRETATIONS AND GENERAL INFO =====
                "version_information": {"order": 1000},
                "resistance_interpretation_section": {"order": 500},
            },
            # Custom plot configuration
            "custom_plot_config": {
                "drug_resistance_table_config": {
                    "title": "HIV Drug Resistance Profile"
                },
                "mutations_table_config": {"title": "Significant Resistance Mutations"},
                "resistance_level_distribution_plot": {
                    "title": "Distribution of Resistance Levels Across Drug Classes"
                },
                "mutation_position_map_plot": {
                    "title": "Genomic Distribution of Resistance Mutations"
                },
                "partial_score_analysis_plot": {
                    "title": "Mutation Contribution to Resistance Scores"
                },
            },
            # Control which columns are visible in tables by default
            "table_columns_visible": {
                "drug_resistance_table": {
                    "Drug": True,
                    "Class": True,
                    "Score": True,
                    "Interpretation": True,
                },
                "significant_mutations": {
                    "Mutation": True,
                    "Type": True,
                    "Position": True,
                    "Is SDRM": True,
                },
            },
            # Custom content ordering
            "custom_content": {
                "order": [
                    "version_information",
                ]
            },
            # Section comments
            "section_comments": {
                # ===== PROTEASE (PR) SECTIONS =====
                "drug_class_overview_pr_table": "Overview of **protease inhibitor (PI) drug class resistance**, highlighting the percentage of drugs affected and resistance severity distribution across all PIs.",
                "drug_resistance_pr_table": "Detailed analysis of **resistance to specific protease inhibitors** with quantitative scoring and clinical interpretations. Critical for PI-based regimen selection.",
                "mutation_clinical_pr_table": "Clinical implications of **protease mutations** organized by mutation importance, showing how each mutation impacts specific PI drugs and treatment outcomes.",
                "mutation_summary_pr_table": "Summary of **mutation types in protease** categorized by Major, Accessory, and Other mutations, with counts and percentages of each type.",
                "mutation_details_pr_table": "Comprehensive listing of all **protease mutations** detected in the sample, including position information, SDRM status, and unusual mutation patterns.",
                "mutation_contribution_pr_table": "Analysis showing how individual **protease mutations contribute** to the total resistance score for each PI drug, identifying key resistance drivers.",
                "mutation_position_map_pr": "Visual mapping of **mutation positions along the protease gene sequence**, revealing patterns and clustering of resistance mutations.",
                # ===== REVERSE TRANSCRIPTASE (RT) SECTIONS =====
                "drug_class_overview_rt_table": "Overview of **RT inhibitor resistance patterns** across both NRTI and NNRTI drug classes, essential for backbone therapy evaluation.",
                "drug_resistance_rt_table": "Comprehensive analysis of **RT inhibitor susceptibility** with detailed scoring for NRTIs and NNRTIs, critical for selection of effective backbone regimens.",
                "mutation_clinical_rt_table": "Clinical significance of **RT mutations** showing their impact on drug efficacy and viral fitness, organized by mutation category.",
                "mutation_summary_rt_table": "Summary of **RT mutation types** found in the sample, showing distribution of Major, Accessory, and polymorphic mutations.",
                "mutation_details_rt_table": "Detailed catalog of all **reverse transcriptase mutations** detected, including position information, SDRM status, and APOBEC-mediated mutations.",
                "mutation_contribution_rt_table": "Quantitative analysis of **how specific RT mutations** contribute to resistance against individual NRTI and NNRTI drugs, highlighting key resistance pathways.",
                "mutation_position_map_rt": "Genomic visualization of **mutation locations across the RT gene**, revealing mutation hotspots and conserved regions.",
                # ===== INTEGRASE (IN) SECTIONS =====
                "drug_class_overview_in_table": "Overview of **integrase inhibitor resistance patterns** detected in the sample, summarizing resistance to this newer drug class.",
                "drug_resistance_in_table": "Analysis of **INSTI drug resistance** with detailed scoring and interpretation, essential for evaluating the efficacy of integrase inhibitors.",
                "mutation_clinical_in_table": "Clinical implications of **integrase mutations** showing how they affect drug binding and enzyme function, with drug-specific impact analysis.",
                "mutation_summary_in_table": "Summary of **integrase mutation types** categorized by clinical importance, showing the distribution of major and accessory resistance mutations.",
                "mutation_details_in_table": "Comprehensive listing of all **integrase mutations** found in the sample, with details on positions and characteristics of each mutation.",
                "mutation_contribution_in_table": "Analysis of **how individual integrase mutations** contribute to overall INSTI resistance, highlighting primary resistance pathways.",
                "mutation_position_map_in": "Visual representation of **mutations along the integrase gene sequence**, showing the distribution of resistance-associated positions.",
                # ===== CAPSID (CA) SECTIONS =====
                "drug_class_overview_ca_table": "Overview of **capsid inhibitor resistance patterns**, examining susceptibility to this emerging drug class targeting HIV capsid assembly and stability.",
                "drug_resistance_ca_table": "Analysis of **resistance to capsid-targeting drugs** with quantitative scoring and interpretation, important for evaluating new treatment options.",
                "mutation_clinical_ca_table": "Clinical significance of **capsid mutations** showing how they impact drug binding sites and capsid protein function.",
                "mutation_summary_ca_table": "Summary of **capsid mutation types** found in the sample, categorized by their impact on drug resistance and viral fitness.",
                "mutation_details_ca_table": "Detailed catalog of all **capsid mutations** detected, including position information and structural implications.",
                "mutation_contribution_ca_table": "Analysis of **how specific capsid mutations** contribute to resistance against individual capsid inhibitor drugs.",
                "mutation_position_map_ca": "Genomic mapping of **mutation positions along the capsid gene sequence**, highlighting key structural and functional domains.",
                # ===== GENERAL SECTIONS =====
                "version_information": "Provides **analysis metadata** including database versions, algorithm information, and sequence details for reproducibility and reference.",
                "resistance_interpretation_section": "Guide to **interpreting drug resistance scores** and levels presented throughout this report, explaining the clinical significance of different resistance categories.",
            },
            # Disable version detection
            "disable_version_detection": False,
            # Disable default intro text
            "intro_text": False,
            # Custom color scheme
            "colours": {
                "plain_content": {
                    "info": "#0d6efd",
                    "warning": "#ff9800",
                    "danger": "#dc3545",
                },
                "status": {"pass": "#28a745", "warn": "#ff9800", "fail": "#dc3545"},
            },
        }

        # Use custom template if requested
        if use_custom_template:
            template_dir = os.path.join(
                os.path.dirname(__file__), "templates", "hyrise"
            )
            if os.path.exists(template_dir):
                self.logger.info(f"Using custom template from: {template_dir}")
                config["template"] = template_dir

        # Create assets directory for any additional files
        assets_dir = os.path.join(self.output_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)

        # Create custom CSS file
        custom_css_path = os.path.join(assets_dir, "hyrise_custom.css")
        with open(custom_css_path, "w") as f:
            f.write(
                """/* HyRISE - Professional Report Styling
 * Custom CSS for MultiQC reports
 * Public Health Agency of Canada
 */

/* Global Typography and Colors */
body {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  line-height: 1.6;
  color: #333;
}

/* Report Header and Navigation */
.navbar-brand {
  font-weight: 600;
  letter-spacing: 0.2px;
}

/* Section Headers and Content */
.mqc-section {
  margin-bottom: 30px;
  border-bottom: 1px solid #e9ecef;
  padding-bottom: 10px;
}

h1, h2, h3, h4, h5, h6 {
  font-weight: 600;
  margin-top: 1.5em;
  margin-bottom: 0.7em;
  color: #2a5a8c;
}

.mqc-section h3 {
  font-size: 22px;
  border-bottom: 1px solid #e9ecef;
  padding-bottom: 8px;
}

.report_comment, 
.mqc-section-comment {
  border-left: 5px solid #3c8dbc;
  background-color: #ecf5fc;
  padding: 15px;
  margin: 15px 0;
  font-size: 14px;
}

/* Tables */
.table {
  margin-bottom: 25px;
  border: 1px solid #dee2e6;
}

.table thead th {
  background-color: #f8f9fa;
  border-bottom: 2px solid #3c8dbc;
  color: #2a5a8c;
  font-weight: 600;
}

.table-bordered>tbody>tr>td, 
.table-bordered>tbody>tr>th, 
.table-bordered>tfoot>tr>td, 
.table-bordered>tfoot>tr>th, 
.table-bordered>thead>tr>td, 
.table-bordered>thead>tr>th {
  border: 1px solid #dee2e6;
}

.table-hover>tbody>tr:hover {
  background-color: #f1f6fb;
}

/* Color Scheme for HyRISE Drug Resistance Levels */
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

/* Mutation Styling */
.position-cell {
  box-sizing: border-box;
  border: 1px solid #eee;
}

.position-major {
  background-color: #d9534f;
  color: white;
}

.position-accessory {
  background-color: #f0ad4e;
  color: white;
}

.position-other {
  background-color: #5bc0de;
  color: white;
}

.position-sdrm {
  border: 2px solid #5cb85c !important;
}

/* Charts and Visualizations */
.hc-plot-wrapper {
  border: 1px solid #dee2e6;
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  margin-bottom: 25px;
}

/* Custom Components */
.summary-card {
  border: 1px solid #dee2e6;
  border-radius: 5px;
  padding: 20px;
  margin-bottom: 25px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.summary-card h4 {
  color: #2a5a8c;
  margin-top: 0;
  padding-bottom: 10px;
  border-bottom: 1px solid #e9ecef;
  margin-bottom: 15px;
}

.executive-summary {
  background-color: #f8f9fa;
  border-left: 5px solid #2a5a8c;
  padding: 15px;
  margin-bottom: 25px;
}

/* Overall Status Messages */
.overall-status {
  padding: 15px;
  margin: 15px 0;
  border-radius: 5px;
  font-weight: 500;
  text-align: center;
}

.status-high {
  background-color: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.status-int {
  background-color: #fff3cd;
  color: #856404;
  border: 1px solid #ffeeba;
}

.status-low {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.status-sus {
  background-color: #d1ecf1;
  color: #0c5460;
  border: 1px solid #bee5eb;
}

/* Tab Navigation for Clinical Implications */
.hyrise-tabs {
  display: flex;
  flex-wrap: wrap;
  border-bottom: 1px solid #dee2e6;
  margin-bottom: 15px;
}

.hyrise-tab {
  padding: 8px 15px;
  cursor: pointer;
  background-color: #f8f9fa;
  border: 1px solid #dee2e6;
  border-bottom: none;
  margin-right: 5px;
  border-radius: 5px 5px 0 0;
  transition: all 0.2s ease;
}

.hyrise-tab.active {
  background-color: #fff;
  border-bottom: 1px solid #fff;
  margin-bottom: -1px;
  font-weight: 600;
  color: #2a5a8c;
}

.hyrise-tab:hover {
  background-color: #e9ecef;
}

.hyrise-tab-content {
  display: none;
  padding: 15px;
  border: 1px solid #dee2e6;
  border-top: none;
  border-radius: 0 0 5px 5px;
}

.hyrise-tab-content.active {
  display: block;
}
/* Mutation Position Map */
.position-map {
  display: flex;
  flex-wrap: wrap;
  margin: 20px 0;
  background-color: #f8f9fa;
  padding: 15px;
  border-radius: 5px;
  border: 1px solid #dee2e6;
}
/* Tooltips and Information Displays */
.position-tooltip {
  background-color: #333;
  color: white;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
  box-shadow: 0 2px 4px rgba(0,0,0,.2);
}
/* Footer Styling */
.footer {
  border-top: 1px solid #dee2e6;
  padding-top: 20px;
  margin-top: 40px;
  color: #6c757d;
}
/* Print Optimizations */
@media print {
  .mqc-toolbox, .side-nav {
    display: none !important;
  }  
  .mainpage {
    margin-left: 0 !important;
    padding: 0 !important;
  }
  .status-high, .status-int, .status-low, .status-sus,
  .high-resistance, .intermediate, .low-resistance, .potential, .susceptible {
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }
  .mqc-section {
    page-break-inside: avoid;
  }
  h2, h3 {
    page-break-after: avoid;
  }
  .summary-card, .executive-summary {
    page-break-inside: avoid;
  }
}
            """
            )

        # Add custom CSS
        config["custom_css_files"] = [
            os.path.join(self.output_dir, "assets", "hyrise_custom.css")
        ]

        # Create the config file
        config_file = os.path.join(self.output_dir, "multiqc_config.yml")
        os.makedirs(os.path.dirname(config_file), exist_ok=True)

        with open(config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        self.config_path = config_file
        self.logger.info(f"Generated MultiQC config at: {config_file}")
        return config_file

    def run_multiqc(self) -> Tuple[bool, str]:
        """
        Run MultiQC with the generated configuration.

        Returns:
            Tuple of (success, output|error message)
        """
        if not self.config_path:
            self.generate_config()

        # Ensure report directory exists
        os.makedirs(self.report_dir, exist_ok=True)

        # Create the MultiQC command
        cmd = f"multiqc {self.output_dir} -o {self.report_dir} --config {self.config_path}"
        self.logger.info(f"Running MultiQC: {cmd}")

        try:
            result = subprocess.run(
                cmd, shell=True, check=True, capture_output=True, text=True
            )
            self.logger.info("MultiQC completed successfully")
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            self.logger.error(f"MultiQC failed: {e.stderr}")
            return False, e.stderr
        except Exception as e:
            self.logger.error(f"Error running MultiQC: {str(e)}")
            return False, str(e)

    def modify_html(
        self, html_path: str, logo_data_uri: str = ""
    ) -> Tuple[bool, Dict[str, bool]]:
        """
        Modify the MultiQC HTML report to customize it for HyRISE.

        Args:
            html_path: Path to the HTML report file
            logo_data_uri: Data URI for the HyRISE logo

        Returns:
            Tuple of (success, modifications_made)
        """
        try:
            with open(html_path, "r", encoding="utf-8") as html:
                soup = BeautifulSoup(html.read(), "html.parser")

            # Track successful modifications
            modifications = {
                "logo": False,
                "title": False,
                "footer": False,
                "about_section": False,
                "toolbox": False,
                "favicon": False,
                "welcome": False,
                "citations": False,
            }

            # 1. Replace logos if we have a logo URI
            if logo_data_uri:
                # Try the direct approach first - look for all images that might be logos
                logo_replaced = False

                # 1. Find all images with data:image base64 src (typical for embedded logos)
                for img_tag in soup.find_all(
                    "img", src=lambda x: x and x.startswith("data:image/")
                ):
                    img_tag["src"] = logo_data_uri
                    logo_replaced = True

                # 2. Try standard selectors as backup
                if not logo_replaced:
                    logo_selectors = [
                        "img#mqc_logo",  # Direct ID selector
                        ".navbar-brand img",  # Logo in navbar
                        "a.navbar-brand img",  # Variations
                        "header img.logo",  # Another variation
                        'img[alt="MultiQC"]',  # By alt text
                    ]

                    for selector in logo_selectors:
                        try:
                            logo_imgs = soup.select(selector)
                            if logo_imgs:
                                for logo_img in logo_imgs:
                                    logo_img["src"] = logo_data_uri
                                logo_replaced = True
                                break
                        except Exception as e:
                            self.logger.debug(
                                f"Error with logo selector '{selector}': {e}"
                            )

                # 3. If all else fails, try to find any small images in the header or navbar
                if not logo_replaced:
                    for img_tag in soup.find_all("img"):
                        parent = img_tag.parent
                        while parent and parent.name not in ["nav", "header", "div"]:
                            if "class" in parent.attrs and any(
                                c in ["navbar", "header", "nav"]
                                for c in parent.get("class", [])
                            ):
                                img_tag["src"] = logo_data_uri
                                logo_replaced = True
                                break
                            parent = parent.parent

                modifications["logo"] = logo_replaced

                # Update favicon
                favicon = soup.find("link", {"rel": "icon", "type": "image/png"})
                if favicon:
                    favicon["href"] = logo_data_uri
                    modifications["favicon"] = True

            # 2. Replace title in document
            title_tag = soup.find("title")
            if title_tag:
                title_tag.string = "HyRISE Report"
                modifications["title"] = True

            # 3. Replace toolbox headers
            # Try different approaches with fallbacks for robustness
            for tag in soup.find_all(["h3", "h4"]):
                if "MultiQC" in tag.text and "Toolbox" in tag.text:
                    tag.string = tag.text.replace("MultiQC", "HyRISE")
                    modifications["toolbox"] = True

            # 4. Replace footer
            footers = soup.select(".footer, footer")
            for footer in footers:
                # Instead of removing entirely, which could break layout,
                # replace with simpler HyRISE footer
                footer.clear()  # Clear all contents
                footer.append(soup.new_tag("p"))
                footer.p.string = f"Generated by HyRISE v{self.version} - HIV Resistance Interpretation & Scoring Engine"
                modifications["footer"] = True

            # 5. Replace "About MultiQC" sections
            for elem in soup.find_all(["h4", "div", "section"]):
                if "About MultiQC" in elem.text:
                    # Replace headers directly
                    if elem.name == "h4":
                        elem.string = "About HyRISE"
                        modifications["about_section"] = True

                    # Try to find and replace content in parent elements
                    parent = elem.parent
                    if parent:
                        for p in parent.find_all("p"):
                            if "MultiQC" in p.text:
                                # Replace MultiQC with HyRISE in paragraph text
                                p.string = p.text.replace("MultiQC", "HyRISE")
                                modifications["about_section"] = True

            # 6. Remove citations section if present
            citation_selectors = [
                "#mqc_citing",  # Direct ID
                'h4:contains("Citing MultiQC")',  # By text
                "blockquote cite",  # Specific citation element
            ]

            for selector in citation_selectors:
                try:
                    elements = soup.select(selector)
                    for elem in elements:
                        # Find the parent section if possible
                        section = elem
                        while section and section.name != "section":
                            section = section.parent

                        # Remove the section or just the element if section not found
                        if section:
                            section.decompose()
                        else:
                            elem.decompose()

                        modifications["citations"] = True
                except Exception as e:
                    self.logger.debug(f"Error with citation selector '{selector}': {e}")

            # 7. Remove welcome sections or replace
            welcome_selectors = ["#mqc_welcome", ".mqc-welcome", "section.welcome"]
            for selector in welcome_selectors:
                try:
                    elements = soup.select(selector)
                    for elem in elements:
                        # Either replace or remove
                        if elem.name == "section":
                            # Create replacement welcome
                            welcome = soup.new_tag("div")
                            welcome["class"] = "welcome"
                            welcome.append(soup.new_tag("h3"))
                            welcome.h3.string = "Welcome to HyRISE Report"
                            welcome.append(soup.new_tag("p"))
                            welcome.p.string = "This report provides a comprehensive analysis of HIV drug resistance mutations."
                            elem.replace_with(welcome)
                        else:
                            elem.decompose()
                        modifications["welcome"] = True
                except Exception as e:
                    self.logger.debug(f"Error with welcome selector '{selector}': {e}")

            # 8. Replace links
            for a_tag in soup.find_all(
                "a",
                href=lambda href: href
                and "multiqc.info" in href
                or "seqera.io" in href,
            ):
                a_tag["href"] = "https://pypi.org/project/hyrise/"

            # 9. Update meta tags
            for meta in soup.find_all("meta"):
                if (
                    meta.get("name") == "description"
                    or meta.get("property") == "og:description"
                ):
                    meta["content"] = (
                        "HIV Resistance Interpretation & Scoring Engine report"
                    )

            # Write the modified HTML
            with open(html_path, "w", encoding="utf-8") as file:
                file.write(str(soup))

            # Log what was modified
            modified_items = [k for k, v in modifications.items() if v]
            self.logger.info(
                f"HTML modifications completed. Modified: {', '.join(modified_items)}"
            )

            return True, modifications

        except Exception as e:
            self.logger.error(f"Error modifying HTML: {str(e)}")
            return False, {}

    def post_process_report(
        self, logo_path: Optional[str] = None
    ) -> Tuple[bool, Dict[str, bool]]:
        """
        Post-process the MultiQC report to customize it for HyRISE.

        Args:
            logo_path: Optional path to a logo file

        Returns:
            Tuple of (success, modifications_made)
        """
        # Find the report HTML file
        html_file = os.path.join(self.report_dir, "multiqc_report.html")
        if not os.path.exists(html_file):
            self.logger.error(f"Report HTML file not found at: {html_file}")
            return False, {}

        # Create a backup before modifying
        backup_file = f"{html_file}.backup"
        shutil.copy2(html_file, backup_file)
        self.logger.info(f"Created backup of original report at: {backup_file}")

        # Get logo data URI
        logo_data_uri = self.embed_logo(logo_path)

        # Modify the HTML
        success, modifications = self.modify_html(html_file, logo_data_uri)

        if not success:
            # Restore from backup on failure
            self.logger.warning("HTML modification failed, restoring from backup")
            shutil.copy2(backup_file, html_file)
            return False, {}

        self.logger.info("HTML report successfully customized for HyRISE")
        return True, modifications

    def generate_report(
        self,
        input_data_path: Optional[str] = None,
        logo_path: Optional[str] = None,
        run_multiqc: bool = True,
        skip_html_mod: bool = False,
        use_custom_template: bool = False,
    ) -> Dict[str, Any]:
        """
        Complete process to generate a HyRISE report.

        Args:
            input_data_path: Path to Sierra JSON data (optional)
            logo_path: Path to custom logo file (optional)
            run_multiqc: Whether to run MultiQC
            skip_html_mod: Whether to skip HTML modifications
            use_custom_template: Whether to use custom MultiQC template

        Returns:
            Dict containing results of the report generation process
        """
        results = {
            "config_generated": False,
            "multiqc_run": False,
            "html_modified": False,
            "report_path": None,
            "errors": [],
        }

        # Step 1: Load input data if provided to extract metadata
        if input_data_path and os.path.exists(input_data_path):
            try:
                import json

                with open(input_data_path, "r") as f:
                    data = json.load(f)
                self.metadata_info = self.create_metadata_summary(data)
                self.logger.info(f"Loaded metadata from: {input_data_path}")
            except Exception as e:
                self.logger.error(f"Error loading input data: {str(e)}")
                results["errors"].append(f"Data loading error: {str(e)}")

        # Step 2: Generate config using the metadata we just extracted (or default values)
        try:
            self.generate_config(use_custom_template)
            results["config_generated"] = True
            self.logger.info("MultiQC config generated successfully")
        except Exception as e:
            self.logger.error(f"Error generating config: {str(e)}")
            results["errors"].append(f"Config generation error: {str(e)}")
            return results

        # Step 2: Run MultiQC if requested
        if run_multiqc:
            success, output = self.run_multiqc()
            results["multiqc_run"] = success
            if not success:
                self.logger.error(f"MultiQC error: {output}")
                results["errors"].append(f"MultiQC error: {output}")
                return results

        # Step 3: Post-process the report if requested
        if run_multiqc and not skip_html_mod:
            success, modifications = self.post_process_report(logo_path)
            results["html_modified"] = success
            if not success:
                self.logger.error("HTML modification failed")
                results["errors"].append("HTML modification error")

        # Set the final report path
        html_file = os.path.join(self.report_dir, "multiqc_report.html")
        if os.path.exists(html_file):
            results["report_path"] = html_file

        return results


def main():
    """Command-line interface for the HyRISE report generator."""
    parser = argparse.ArgumentParser(description="HyRISE MultiQC Report Generator")
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input directory containing MultiQC data files",
    )
    parser.add_argument(
        "-o", "--output", required=True, help="Output directory for report"
    )
    parser.add_argument("-d", "--data", help="Path to Sierra JSON data file (optional)")
    parser.add_argument("-s", "--sample", help="Sample name for the report")
    parser.add_argument("-e", "--email", help="Contact email for the report")
    parser.add_argument("-l", "--logo", help="Path to custom logo file (PNG or SVG)")
    parser.add_argument(
        "-v", "--version", default="0.1.0", help="HyRISE version number"
    )
    parser.add_argument(
        "--skip-multiqc", action="store_true", help="Skip running MultiQC"
    )
    parser.add_argument(
        "--skip-html-mod", action="store_true", help="Skip HTML modifications"
    )
    parser.add_argument(
        "--use-template", action="store_true", help="Use custom MultiQC template"
    )

    args = parser.parse_args()

    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)

    # Initialize the report generator
    generator = HyRISEReportGenerator(
        output_dir=args.output,
        version=args.version,
        sample_name=args.sample,
        contact_email=args.email,
    )

    # Generate the report - now our function will handle the metadata extraction
    results = generator.generate_report(
        input_data_path=args.data,
        logo_path=args.logo,
        run_multiqc=not args.skip_multiqc,
        skip_html_mod=args.skip_html_mod,
        use_custom_template=args.use_template,
    )

    # Print results
    if results["errors"]:
        print("Errors occurred during report generation:")
        for error in results["errors"]:
            print(f"  - {error}")
        return 1

    print("\nReport Generation Summary:")
    print(f"  Config generated: {'Yes' if results['config_generated'] else 'No'}")
    print(f"  MultiQC run: {'Yes' if results['multiqc_run'] else 'No'}")
    print(f"  HTML modified: {'Yes' if results['html_modified'] else 'No'}")

    if results["report_path"]:
        print(f"\nReport is available at: {results['report_path']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

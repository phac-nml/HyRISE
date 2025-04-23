"""
Enhanced HyRISE MultiQC Report Generator with robust HTML modifications
and integrated command-line interface.
"""

import os
import sys
import re
import shutil
import argparse
import subprocess
import yaml
import base64
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional, Union
from bs4 import BeautifulSoup, Comment
from rich.console import Console
from hyrise import __version__


class HyRISEReportGenerator:
    """Class to handle the generation and customization of MultiQC reports for HyRISE."""

    def __init__(
        self,
        output_dir: str,
        version: str = __version__,
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
            # "validation": data.get("validationResults", []),
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
                # "validation": [],
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
            # Output file configuration
            "output_fn_name": "hyrise_resistance_report.html",  # Custom filename for better identification
            "data_dir_name": "hyrise_data",  # Custom data directory name
            "plots_dir_name": "hyrise_plots",  # Custom plots directory name
            "data_format": "tsv",  # TSV format for data exports
            # Data handling options
            "make_data_dir": True,  # Create a data directory for report data
            "zip_data_dir": True,  # Zip the data directory for easy sharing
            "data_dump_file": True,  # Create a data dump file for further analysis
            # "export_plots": True,  # Export plots as standalone files for publications
            # Performance options
            "profile_runtime": False,  # Profile runtime for optimization
            # Built-in MultiQC customization options
            "show_analysis_paths": False,
            "show_analysis_time": True,
            "skip_generalstats": True,
            "collapse_tables": False,  # Keep tables expanded for better visibility
            # Table display options
            "max_table_rows": 1000,  # Increase from default 500 for larger HIV datasets
            "max_configurable_table_columns": 250,  # Increase from default for complex resistance tables
            "decimalPoint_format": ".",  # Ensure consistent decimal formatting
            "thousandsSep_format": ",",  # Ensure consistent thousands separator
            # Use built-in multiQC features for branding
            "custom_logo_url": "https://pypi.org/project/hyrise/",
            "custom_logo_title": "HyRISE - HIV Resistance Interpretation & Scoring Engine",
            "introduction": "This report was generated by HyRISE, the HIV Resistance Interpretation & Scoring Engine.",
            # Report header info
            "report_header_info": header,
            # Visualization options
            "plots_force_interactive": True,  # Force interactive plots for better analysis
            "plots_flat_numseries": 5000,  # Support more data series for complex HIV analysis
            "plots_defer_loading_numseries": 200,  # Improve loading performance for large datasets
            "lineplot_number_of_points_to_hide_markers": 25,  # Hide markers on dense line plots
            "barplot_legend_on_bottom": True,  # Place legend at bottom for better space usage
            "plots_export_font_scale": 1.25,  # Slightly larger fonts for better readability in exported plots
            # Section ordering
            "report_section_order": {
                # Main sections that will act as dropdown parent headers
                "pr_gene_section": {
                    "order": 4000,
                    "section_name": "Protease (PR) Gene Analysis",
                },
                "rt_gene_section": {
                    "order": 3000,
                    "section_name": "Reverse Transcriptase (RT) Gene Analysis",
                },
                "in_gene_section": {
                    "order": 2000,
                    "section_name": "Integrase (IN) Gene Analysis",
                },
                "ca_gene_section": {
                    "order": 1000,
                    "section_name": "Capsid (CA) Gene Analysis",
                },
                "interpretation_section": {
                    "order": 500,
                    "section_name": "Interpretation Guides",
                },
                # ===== PROTEASE (PR) SUBSECTIONS - notice they reference the parent =====
                "drug_class_overview_pr_table": {
                    "parent": "pr_gene_section",
                    "section_name": "Drug Class Overview",
                },
                "drug_resistance_pr_table": {
                    "parent": "pr_gene_section",
                    "section_name": "Resistance Profile",
                    "after": "drug_class_overview_pr_table",
                },
                "mutation_clinical_pr_table": {
                    "parent": "pr_gene_section",
                    "section_name": "Clinical Implications",
                    "after": "drug_resistance_pr_table",
                },
                "mutation_summary_pr_table": {
                    "parent": "pr_gene_section",
                    "section_name": "Mutation Summary",
                    "after": "mutation_clinical_pr_table",
                },
                "mutation_details_pr_table": {
                    "parent": "pr_gene_section",
                    "section_name": "Mutation Details",
                    "after": "mutation_summary_pr_table",
                },
                "mutation_contribution_pr_table": {
                    "parent": "pr_gene_section",
                    "section_name": "Resistance Contribution",
                    "after": "mutation_details_pr_table",
                },
                "mutation_position_map_pr": {
                    "parent": "pr_gene_section",
                    "section_name": "Position Mapping",
                    "after": "mutation_contribution_pr_table",
                },
                # ===== REVERSE TRANSCRIPTASE (RT) SUBSECTIONS =====
                "drug_class_overview_rt_table": {
                    "parent": "rt_gene_section",
                    "section_name": "Drug Class Overview",
                },
                "drug_resistance_rt_table": {
                    "parent": "rt_gene_section",
                    "section_name": "Resistance Profile",
                    "after": "drug_class_overview_rt_table",
                },
                "mutation_clinical_rt_table": {
                    "parent": "rt_gene_section",
                    "section_name": "Clinical Implications",
                    "after": "drug_resistance_rt_table",
                },
                "mutation_summary_rt_table": {
                    "parent": "rt_gene_section",
                    "section_name": "Mutation Summary",
                    "after": "mutation_clinical_rt_table",
                },
                "mutation_details_rt_table": {
                    "parent": "rt_gene_section",
                    "section_name": "Mutation Details",
                    "after": "mutation_summary_rt_table",
                },
                "mutation_contribution_rt_table": {
                    "parent": "rt_gene_section",
                    "section_name": "Resistance Contribution",
                    "after": "mutation_details_rt_table",
                },
                "mutation_position_map_rt": {
                    "parent": "rt_gene_section",
                    "section_name": "Position Mapping",
                    "after": "mutation_contribution_rt_table",
                },
                # ===== INTEGRASE (IN) SUBSECTIONS =====
                "drug_class_overview_in_table": {
                    "parent": "in_gene_section",
                    "section_name": "Drug Class Overview",
                },
                "drug_resistance_in_table": {
                    "parent": "in_gene_section",
                    "section_name": "Resistance Profile",
                    "after": "drug_class_overview_in_table",
                },
                "mutation_clinical_in_table": {
                    "parent": "in_gene_section",
                    "section_name": "Clinical Implications",
                    "after": "drug_resistance_in_table",
                },
                "mutation_summary_in_table": {
                    "parent": "in_gene_section",
                    "section_name": "Mutation Summary",
                    "after": "mutation_clinical_in_table",
                },
                "mutation_details_in_table": {
                    "parent": "in_gene_section",
                    "section_name": "Mutation Details",
                    "after": "mutation_summary_in_table",
                },
                "mutation_contribution_in_table": {
                    "parent": "in_gene_section",
                    "section_name": "Resistance Contribution",
                    "after": "mutation_details_in_table",
                },
                "mutation_position_map_in": {
                    "parent": "in_gene_section",
                    "section_name": "Position Mapping",
                    "after": "mutation_contribution_in_table",
                },
                # ===== CAPSID (CA) SUBSECTIONS =====
                "drug_class_overview_ca_table": {
                    "parent": "ca_gene_section",
                    "section_name": "Drug Class Overview",
                },
                "drug_resistance_ca_table": {
                    "parent": "ca_gene_section",
                    "section_name": "Resistance Profile",
                    "after": "drug_class_overview_ca_table",
                },
                "mutation_clinical_ca_table": {
                    "parent": "ca_gene_section",
                    "section_name": "Clinical Implications",
                    "after": "drug_resistance_ca_table",
                },
                "mutation_summary_ca_table": {
                    "parent": "ca_gene_section",
                    "section_name": "Mutation Summary",
                    "after": "mutation_clinical_ca_table",
                },
                "mutation_details_ca_table": {
                    "parent": "ca_gene_section",
                    "section_name": "Mutation Details",
                    "after": "mutation_summary_ca_table",
                },
                "mutation_contribution_ca_table": {
                    "parent": "ca_gene_section",
                    "section_name": "Resistance Contribution",
                    "after": "mutation_details_ca_table",
                },
                "mutation_position_map_ca": {
                    "parent": "ca_gene_section",
                    "section_name": "Position Mapping",
                    "after": "mutation_contribution_ca_table",
                },
                # ===== INTERPRETATION GUIDES SUBSECTIONS =====
                "version_information": {
                    "parent": "interpretation_section",
                    "section_name": "Analysis Information",
                },
                "resistance_interpretation_table": {
                    "parent": "interpretation_section",
                    "section_name": "Resistance Levels Guide",
                    "after": "version_information",
                },
                "mutation_type_table": {
                    "parent": "interpretation_section",
                    "section_name": "Mutation Types Guide",
                    "after": "resistance_interpretation_table",
                },
                "drug_class_info_table": {
                    "parent": "interpretation_section",
                    "section_name": "Drug Classes Guide",
                    "after": "mutation_type_table",
                },
            },
            # Section comments
            "section_comments": {
                # ===== PROTEASE (PR) SECTIONS =====
                "drug_class_overview_pr_table": "Overview of **protease inhibitor (PI) drug class resistance**, highlighting percentages of affected drugs and resistance severity distribution. This section quantifies resistance across the PI class with priority drug indicators.",
                "drug_resistance_pr_table": "Detailed analysis of **resistance to specific protease inhibitors** with quantitative scoring, clinical interpretations, and weighted scores based on drug importance. Essential for optimizing PI-based regimen selection.",
                "mutation_clinical_pr_table": "Clinical implications of **protease mutations** organized by importance (Major, Accessory, Other), showing specific impacts on drug efficacy with evidence-based commentary extracted from Stanford HIV database.",
                "mutation_summary_pr_table": "Statistical breakdown of **mutation types in protease** with counts, percentages, and representative examples. Includes SDRM and APOBEC-mediated mutation categorization with clinical context.",
                "mutation_details_pr_table": "Comprehensive catalog of all detected **protease mutations** with position information, mutation characteristics, and special classifications (SDRM, APOBEC, unusual variants) in a filterable format.",
                "mutation_contribution_pr_table": "Quantitative analysis showing how individual **protease mutations contribute** to resistance scores for each PI, identifying key resistance drivers and their relative impact percentages.",
                "mutation_position_map_pr": "Interactive visualization mapping **mutations along the protease gene sequence** with color-coding by type, special border indicators for SDRMs, and detailed tooltips for each mutation position.",
                # ===== REVERSE TRANSCRIPTASE (RT) SECTIONS =====
                "drug_class_overview_rt_table": "Overview of **RT inhibitor resistance patterns** across both NRTI and NNRTI drug classes, with resistance metrics for backbone therapy evaluation and priority drug indicators.",
                "drug_resistance_rt_table": "Comprehensive analysis of **RT inhibitor susceptibility** with detailed scoring for NRTIs and NNRTIs, highlighting both standard and weighted resistance scores based on clinical importance.",
                "mutation_clinical_rt_table": "Clinical significance of **RT mutations** showing their impact on drug efficacy and viral fitness, organized by mutation category with linked drug-specific effects and Stanford database commentary.",
                "mutation_summary_rt_table": "Statistical summary of **RT mutation types** with distribution of Major, Accessory, and polymorphic mutations, including special categories for TAMs, NNRTI-specific, and APOBEC-mediated mutations.",
                "mutation_details_rt_table": "Detailed inventory of all **reverse transcriptase mutations** with position information, mutation properties, and special classifications in a searchable, filterable format designed for research use.",
                "mutation_contribution_rt_table": "Mutation-specific analysis showing **how RT mutations contribute** to resistance against individual NRTI and NNRTI drugs, quantifying percentage contributions to total resistance scores.",
                "mutation_position_map_rt": "Interactive genomic visualization of **mutation locations across the RT gene**, revealing mutation hotspots and clinically significant regions with detailed position-specific information.",
                # ===== INTEGRASE (IN) SECTIONS =====
                "drug_class_overview_in_table": "Overview of **integrase inhibitor resistance patterns** with metrics assessing impact on both first-generation (RAL, EVG) and second-generation (DTG, BIC, CAB) integrase inhibitors.",
                "drug_resistance_in_table": "Analysis of **INSTI drug resistance** with detailed scoring and interpretation, providing essential metrics for evaluating efficacy of individual integrase inhibitors with clinical priority weighting.",
                "mutation_clinical_in_table": "Clinical implications of **integrase mutations** demonstrating effects on drug binding and enzyme function, with drug-specific impact analysis and pathway resistance patterns.",
                "mutation_summary_in_table": "Statistical breakdown of **integrase mutation types** by clinical importance, showing distribution of major pathway mutations (Y143, Q148, N155) and accessory resistance mutations.",
                "mutation_details_in_table": "Comprehensive catalog of all **integrase mutations** with position information, resistance characteristics, and special classifications organized for efficient clinical interpretation.",
                "mutation_contribution_in_table": "Quantitative assessment of **how specific integrase mutations** contribute to INSTI resistance, highlighting primary and accessory resistance pathways with their relative contributions.",
                "mutation_position_map_in": "Interactive mapping of **mutations along the integrase gene sequence**, visualizing the distribution of resistance-associated positions with functional domain context and tooltips.",
                # ===== CAPSID (CA) SECTIONS =====
                "drug_class_overview_ca_table": "Overview of **capsid inhibitor resistance patterns**, examining susceptibility to this emerging drug class targeting HIV capsid assembly, with metrics focused on lenacapavir (LEN) and future capsid inhibitors.",
                "drug_resistance_ca_table": "Analysis of **resistance to capsid-targeting drugs** with quantitative scoring and clinical interpretation, important for evaluating these newer long-acting treatment options.",
                "mutation_clinical_ca_table": "Clinical significance of **capsid mutations** showing impact on drug binding sites and capsid protein function, with detailed commentary on structural and functional consequences.",
                "mutation_summary_ca_table": "Statistical overview of **capsid mutation types** categorized by impact on drug resistance and viral fitness, showing distribution across capsid functional domains.",
                "mutation_details_ca_table": "Comprehensive inventory of all detected **capsid mutations** with position information, structural implications, and relationship to known resistance pathways in a research-grade format.",
                "mutation_contribution_ca_table": "Quantitative analysis of **how specific capsid mutations** contribute to resistance against individual capsid inhibitor drugs, with percentage contributions to total resistance scores.",
                "mutation_position_map_ca": "Interactive visualization of **mutation positions along the capsid gene sequence**, highlighting key structural and functional domains with protein structure context where available.",
                # ===== GENERAL SECTIONS =====
                "version_information": "Provides **analysis metadata** including Stanford HIV database version, algorithm parameters, sequence quality metrics, and processing details for reproducibility and reference.",
                "resistance_interpretation_section": "Comprehensive guide to **interpreting drug resistance scores** and levels throughout this report, explaining clinical significance of resistance categories with evidence-based interpretation guidelines.",
            },
            # Disable version detection
            "disable_version_detection": False,
            # Disable default intro text
            # "intro_text": False,
            # Enhanced color scheme with more professional clinical colors
            "colours": {
                "plain_content": {
                    "info": "#0d6efd",
                    "warning": "#ff9800",
                    "danger": "#dc3545",
                },
                "status": {"pass": "#28a745", "warn": "#ff9800", "fail": "#dc3545"},
            },
            # Enhanced conditional formatting colors
            "table_cond_formatting_colours": [
                {
                    "blue": "#337ab7",
                    "lbue": "#5bc0de",
                    "pass": "#28a745",
                    "warn": "#f0ad4e",
                    "fail": "#d9534f",
                    "susceptible": "#28a745",
                    "potential": "#5bc0de",
                    "low": "#ffcc00",
                    "intermediate": "#ff9900",
                    "high": "#dc3545",
                }
            ],
            # Additional conditional formatting rules
            "table_cond_formatting_rules": {
                "all_columns": {
                    "pass": [
                        {"s_eq": "pass"},
                        {"s_eq": "true"},
                        {"s_eq": "yes"},
                        {"s_eq": "ok"},
                        {"s_eq": "Susceptible"},
                    ],
                    "warn": [
                        {"s_eq": "warn"},
                        {"s_eq": "unknown"},
                        {"s_eq": "Low-Level"},
                        {"s_eq": "Potential Low-Level"},
                    ],
                    "fail": [
                        {"s_eq": "fail"},
                        {"s_eq": "false"},
                        {"s_eq": "no"},
                        {"s_eq": "High-Level"},
                        {"s_eq": "Intermediate"},
                    ],
                },
                "Resistance Level": {
                    "susceptible": [{"s_eq": "Susceptible"}],
                    "potential": [{"s_eq": "Potential Low-Level"}],
                    "low": [{"s_eq": "Low-Level"}],
                    "intermediate": [{"s_eq": "Intermediate"}],
                    "high": [{"s_eq": "High-Level"}],
                },
            },
            # File patterns to ignore
            "fn_ignore_files": [
                "*.bam",
                "*.bai",
                "*.fq.gz",
                "*.fastq.gz",
                "*.fa",
                "*.pdf",
                "*.parquet",
            ],
            # Add highlight patterns to emphasize important values
            "highlight_patterns": ["High-Level", "Intermediate", "SDRM"],
            "highlight_colors": ["#f8d7da", "#fff3cd", "#d1e7dd"],
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

        This function transforms a standard MultiQC report into a HyRISE-branded report
        while maintaining proper attribution and ensuring professional presentation.
        The function applies modifications systematically with fallbacks for future MultiQC versions.

        Args:
            html_path: Path to the HTML report file
            logo_data_uri: Data URI for the HyRISE logo

        Returns:
            Tuple of (success, modifications_made)
        """
        try:
            self.logger.info(f"Starting HTML modifications on {html_path}")

            # Track modifications for reporting
            modifications = {
                "logo": False,
                "title": False,
                "footer": False,
                "about_section": False,
                "toolbox": False,
                "favicon": False,
                "welcome": False,
                "citations": False,
                "navbar_version": False,
                "meta_tags": False,
                "lead_paragraph": False,
                "links": False,
            }

            # Read and parse the HTML file
            try:
                with open(html_path, "r", encoding="utf-8") as html_file:
                    html_content = html_file.read()

                # Parse with appropriate parser
                soup = BeautifulSoup(html_content, "html.parser")
                self.logger.info("Successfully parsed HTML document")
            except Exception as e:
                self.logger.error(f"Failed to read or parse HTML file: {str(e)}")
                return False, {}

            # Initialize a backup in case restoration is needed
            try:
                backup_path = f"{html_path}.backup"
                shutil.copy2(html_path, backup_path)
                self.logger.info(f"Created backup at {backup_path}")
            except Exception as e:
                self.logger.warning(f"Could not create backup: {str(e)}")

            # 1. MODIFY PAGE TITLE
            try:
                title_tag = soup.find("title")
                if title_tag:
                    original_title = title_tag.string
                    if "MultiQC" in original_title:
                        new_title = original_title.replace("MultiQC", "HyRISE")
                        title_tag.string = new_title
                    else:
                        title_tag.string = (
                            "HyRISE: HIV Resistance Interpretation & Scoring Engine"
                        )

                    modifications["title"] = True
                    self.logger.info(f"Updated page title: {title_tag.string}")
            except Exception as e:
                self.logger.error(f"Error updating page title: {str(e)}")

            # 2. REPLACE META TAGS
            try:
                meta_tags_modified = False
                meta_updates = {
                    "description": "HyRISE: HIV Resistance Interpretation & Scoring Engine report providing comprehensive analysis of HIV drug resistance mutations",
                    "author": "National Microbiology Laboratory, Public Health Agency of Canada",
                    "keywords": "HIV, drug resistance, mutation analysis, antiretroviral therapy",
                }

                for meta in soup.find_all("meta"):
                    if meta.get("name") in meta_updates:
                        meta["content"] = meta_updates[meta.get("name")]
                        meta_tags_modified = True
                    elif meta.get("property") == "og:description":
                        meta["content"] = meta_updates["description"]
                        meta_tags_modified = True
                    elif meta.get("property") == "og:title" and "MultiQC" in meta.get(
                        "content", ""
                    ):
                        meta["content"] = meta["content"].replace("MultiQC", "HyRISE")
                        meta_tags_modified = True

                # Add missing meta tags
                head_tag = soup.find("head")
                if head_tag:
                    for name, content in meta_updates.items():
                        if not soup.find("meta", attrs={"name": name}):
                            new_meta = soup.new_tag("meta")
                            new_meta["name"] = name
                            new_meta["content"] = content
                            head_tag.append(new_meta)
                            meta_tags_modified = True

                modifications["meta_tags"] = meta_tags_modified
                if meta_tags_modified:
                    self.logger.info(
                        "Updated meta tags for improved SEO and attribution"
                    )
            except Exception as e:
                self.logger.error(f"Error updating meta tags: {str(e)}")

            # 3. ADD FAVICON
            try:
                # Find favicon file with multiple fallbacks
                favicon_paths = [
                    Path("src/hyrise/core/assets/favicon.svg"),
                    Path(__file__).parent / "assets" / "favicon.svg",
                    Path(__file__).parent.parent / "assets" / "favicon.svg",
                    Path(os.path.dirname(os.path.abspath(__file__)))
                    / "assets"
                    / "favicon.svg",
                ]

                favicon_path = next((p for p in favicon_paths if p.exists()), None)
                favicon_data_uri = ""

                if favicon_path:
                    try:
                        with open(favicon_path, "rb") as f:
                            favicon_content = f.read()
                            encoded_favicon = base64.b64encode(favicon_content).decode(
                                "utf-8"
                            )
                            favicon_data_uri = (
                                f"data:image/svg+xml;base64,{encoded_favicon}"
                            )
                        self.logger.info(f"Loaded favicon from {favicon_path}")
                    except Exception as e:
                        self.logger.warning(f"Failed to load favicon file: {str(e)}")

                # Fallback to logo if no favicon found
                if not favicon_data_uri and logo_data_uri:
                    favicon_data_uri = logo_data_uri
                    self.logger.info("Using logo as favicon (fallback)")

                if favicon_data_uri:
                    head_tag = soup.find("head")
                    if head_tag:
                        # Remove existing favicons
                        for link in head_tag.find_all(
                            "link", rel=lambda r: r and "icon" in r.lower()
                        ):
                            link.decompose()

                        # Add new favicon
                        new_favicon = soup.new_tag("link")
                        new_favicon["rel"] = "icon"
                        new_favicon["type"] = (
                            "image/svg+xml"
                            if "svg+xml" in favicon_data_uri
                            else "image/png"
                        )
                        new_favicon["href"] = favicon_data_uri
                        head_tag.append(new_favicon)

                        modifications["favicon"] = True
                        self.logger.info("Added custom favicon")
                else:
                    self.logger.warning("No favicon source available")
            except Exception as e:
                self.logger.error(f"Error setting favicon: {str(e)}")

            # 4. REPLACE LOGOS WITH MULTIPLE SELECTOR STRATEGIES
            if logo_data_uri:
                try:
                    logo_replaced = False

                    # Strategy 1: Use structured selectors with hierarchy
                    logo_hierarchies = [
                        ("h1 > a > img", "Header logo in h1"),
                        (".navbar-brand > img", "Navbar brand logo"),
                        (".navbar-header > a > img", "Navbar header logo"),
                        (".header-logo > img", "Header logo class"),
                        (".logo-container img", "Logo container"),
                    ]

                    for selector, description in logo_hierarchies:
                        logo_imgs = soup.select(selector)
                        if logo_imgs:
                            for img in logo_imgs:
                                img["src"] = logo_data_uri
                                if img.get("alt") and "MultiQC" in img["alt"]:
                                    img["alt"] = img["alt"].replace("MultiQC", "HyRISE")
                                logo_replaced = True
                                self.logger.info(f"Replaced logo: {description}")

                    # Strategy 2: Find logos by attribute patterns
                    if not logo_replaced:
                        for img_tag in soup.find_all("img"):
                            # Check for logos by source, alt text, or class
                            img_src = img_tag.get("src", "")
                            img_alt = img_tag.get("alt", "")
                            img_class = " ".join(img_tag.get("class", []))

                            if (
                                "logo" in img_src.lower()
                                or "MultiQC" in img_alt
                                or "logo" in img_class.lower()
                                or img_src.startswith("data:image/")
                            ):
                                img_tag["src"] = logo_data_uri
                                if "MultiQC" in img_alt:
                                    img_tag["alt"] = img_alt.replace(
                                        "MultiQC", "HyRISE"
                                    )
                                logo_replaced = True
                                self.logger.info(f"Replaced logo by attribute pattern")

                    # Strategy 3: Look in specific containers
                    if not logo_replaced:
                        containers = [
                            ".navbar",
                            ".navbar-header",
                            "header",
                            ".header",
                            "#header",
                            ".branding",
                            ".brand",
                        ]

                        for container in containers:
                            elements = soup.select(container)
                            for element in elements:
                                for img in element.find_all("img"):
                                    img["src"] = logo_data_uri
                                    logo_replaced = True
                                    self.logger.info(
                                        f"Replaced logo in container: {container}"
                                    )

                    modifications["logo"] = logo_replaced
                    if not logo_replaced:
                        self.logger.warning("Could not find logos to replace")
                except Exception as e:
                    self.logger.error(f"Error replacing logos: {str(e)}")

            # 5. UPDATE VERSION INFORMATION
            try:
                version_replaced = False

                # Strategy 1: Look for version in small tags within h1
                for h1 in soup.find_all("h1"):
                    for small in h1.find_all("small"):
                        text = small.get_text().strip()
                        if text.startswith("v") or "version" in text.lower():
                            small.string = f"v{self.version}"
                            version_replaced = True
                            self.logger.info(
                                f"Updated version in header: {small.string}"
                            )

                # Strategy 2: Look for version pattern in any text node
                if not version_replaced:
                    version_pattern = re.compile(r"\bv\d+\.\d+(\.\d+)?")

                    for text in soup.find_all(string=version_pattern):
                        if not isinstance(text, Comment):  # Skip comment nodes
                            parent = text.parent
                            new_text = version_pattern.sub(f"v{self.version}", text)
                            text.replace_with(new_text)
                            version_replaced = True
                            self.logger.info(
                                f"Updated version text with pattern: {parent.name}"
                            )

                # Strategy 3: Look for version in footer
                if not version_replaced:
                    footer = soup.find("footer") or soup.find(class_="footer")
                    if footer:
                        for p in footer.find_all("p"):
                            if "version" in p.text.lower():
                                # Replace just the version number, preserving the rest of the text
                                text = p.get_text()
                                new_text = re.sub(
                                    r"\d+\.\d+(\.\d+)?", self.version, text
                                )
                                p.string = new_text
                                version_replaced = True
                                self.logger.info(f"Updated version in footer")

                modifications["navbar_version"] = version_replaced
            except Exception as e:
                self.logger.error(f"Error updating version information: {str(e)}")

            # 6. REMOVE LEAD PARAGRAPH ABOUT MULTIQC
            try:
                lead_removed = False
                # Multiple strategies to find and remove the lead paragraph

                # Strategy 1: Find by class and content
                lead_paras = soup.find_all("p", class_="lead")
                for para in lead_paras:
                    text = para.get_text().lower()
                    if any(
                        phrase in text
                        for phrase in ["multiqc", "aggregate results", "bioinformatics"]
                    ):
                        para.decompose()
                        lead_removed = True
                        self.logger.info(
                            "Removed MultiQC lead paragraph by class and content"
                        )

                # Strategy 2: Find by content in any paragraph
                if not lead_removed:
                    intro_phrases = [
                        "multiqc is a",
                        "multiqc generates",
                        "modular tool to aggregate",
                        "bioinformatics analyses",
                    ]

                    for p in soup.find_all("p"):
                        text = p.get_text().lower()
                        if any(phrase in text for phrase in intro_phrases):
                            p.decompose()
                            lead_removed = True
                            self.logger.info(
                                "Removed MultiQC description paragraph by content"
                            )

                # Strategy 3: Find by location and basic structure
                if not lead_removed:
                    # Look for paragraphs in the main content area that mention MultiQC
                    main_content = soup.find(id="mainContent") or soup.find(
                        class_="mainpage"
                    )
                    if main_content:
                        for p in main_content.find_all(
                            "p", limit=3
                        ):  # Check first few paragraphs
                            if "MultiQC" in p.get_text():
                                p.decompose()
                                lead_removed = True
                                self.logger.info(
                                    "Removed MultiQC paragraph from main content"
                                )

                modifications["lead_paragraph"] = lead_removed
            except Exception as e:
                self.logger.error(f"Error removing lead paragraph: {str(e)}")

            # 7. REPLACE TOOLBOX HEADERS
            try:
                toolbox_replaced = False

                # Strategy 1: Use class-based selectors
                toolbox_selectors = [
                    ".mqc-toolbox h3",
                    ".mqc-toolbox h4",
                    "#mqc_toolbox h3",
                    "#mqc_toolbox h4",
                    ".mqc_toolbox h3",
                    ".mqc_toolbox h4",
                ]

                for selector in toolbox_selectors:
                    headers = soup.select(selector)
                    for header in headers:
                        if "MultiQC" in header.get_text():
                            header.string = header.get_text().replace(
                                "MultiQC", "HyRISE"
                            )
                            toolbox_replaced = True
                            self.logger.info(
                                f"Replaced toolbox header with selector: {selector}"
                            )

                # Strategy 2: Find by content
                if not toolbox_replaced:
                    for tag in soup.find_all(["h3", "h4"]):
                        if (
                            "toolbox" in tag.get_text().lower()
                            and "MultiQC" in tag.get_text()
                        ):
                            tag.string = tag.get_text().replace("MultiQC", "HyRISE")
                            toolbox_replaced = True
                            self.logger.info(
                                f"Replaced toolbox header by content match"
                            )

                modifications["toolbox"] = toolbox_replaced
            except Exception as e:
                self.logger.error(f"Error updating toolbox headers: {str(e)}")

            # 8. UPDATE FOOTER
            try:
                footer_replaced = False

                # Strategy 1: Find by class
                footer = soup.find(class_="footer")
                if footer:
                    container = footer.find(class_="container-fluid") or footer
                    if container:
                        # Preserve footer structure but replace content
                        container.clear()

                        # Add our custom content with professional styling
                        p1 = soup.new_tag("p")
                        p1.string = f"Generated by HyRISE v{self.version} - HIV Resistance Interpretation & Scoring Engine"
                        container.append(p1)

                        p2 = soup.new_tag("p")
                        p2.string = "Developed by the National Microbiology Laboratory, Public Health Agency of Canada"
                        container.append(p2)

                        # Add attribution to MultiQC
                        p3 = soup.new_tag("p", **{"class": "small text-muted"})
                        p3.string = "Powered by MultiQC, a modular framework for bioinformatics reporting"
                        container.append(p3)

                        footer_replaced = True
                        self.logger.info(
                            "Replaced footer content with professional attribution"
                        )

                # Strategy 2: Find by tag
                if not footer_replaced:
                    footer = soup.find("footer")
                    if footer:
                        footer.clear()

                        div = soup.new_tag("div", **{"class": "container-fluid"})

                        p1 = soup.new_tag("p")
                        p1.string = f"Generated by HyRISE v{self.version} - HIV Resistance Interpretation & Scoring Engine"
                        div.append(p1)

                        p2 = soup.new_tag("p")
                        p2.string = "Developed by the National Microbiology Laboratory, Public Health Agency of Canada"
                        div.append(p2)

                        p3 = soup.new_tag("p", **{"class": "small text-muted"})
                        p3.string = "Powered by MultiQC, a modular framework for bioinformatics reporting"
                        div.append(p3)

                        footer.append(div)
                        footer_replaced = True
                        self.logger.info("Replaced footer by tag")

                # Strategy 3: Create footer if not found
                if not footer_replaced:
                    body = soup.find("body")
                    if body:
                        # Check if last child is already a footer
                        last_child = list(body.children)[-1]
                        if (
                            last_child.name != "footer"
                            and not last_child.get("class") == "footer"
                        ):
                            # Create new footer
                            footer = soup.new_tag("footer", **{"class": "footer"})
                            div = soup.new_tag("div", **{"class": "container-fluid"})

                            p1 = soup.new_tag("p")
                            p1.string = f"Generated by HyRISE v{self.version} - HIV Resistance Interpretation & Scoring Engine"
                            div.append(p1)

                            p2 = soup.new_tag("p")
                            p2.string = "Developed by the National Microbiology Laboratory, Public Health Agency of Canada"
                            div.append(p2)

                            p3 = soup.new_tag("p", **{"class": "small text-muted"})
                            p3.string = "Powered by MultiQC, a modular framework for bioinformatics reporting"
                            div.append(p3)

                            footer.append(div)
                            body.append(footer)
                            footer_replaced = True
                            self.logger.info("Created new footer")

                modifications["footer"] = footer_replaced
            except Exception as e:
                self.logger.error(f"Error updating footer: {str(e)}")

            # 9. UPDATE ABOUT SECTION WITH PROPER ATTRIBUTION
            try:
                about_replaced = False

                # Strategy 1: Find by ID
                about_section = soup.find(id="mqc_about")
                if about_section:
                    about_section.clear()

                    # Add header
                    header = soup.new_tag("h4")
                    header.string = "About HyRISE"
                    about_section.append(header)

                    # Add content
                    p1 = soup.new_tag("p")
                    p1.string = f"This report was generated using HyRISE v{self.version} (HIV Resistance Interpretation & Scoring Engine)."
                    about_section.append(p1)

                    p2 = soup.new_tag("p")
                    p2.string = "HyRISE provides comprehensive analysis of HIV drug resistance mutations, offering detailed visualizations and clinical interpretations to support treatment decisions."
                    about_section.append(p2)

                    # Add repository links
                    links_div = soup.new_tag("div", **{"class": "well well-sm"})
                    links_list = soup.new_tag("ul", **{"class": "list-unstyled"})

                    # GitHub link
                    li1 = soup.new_tag("li")
                    icon1 = soup.new_tag("i", **{"class": "fa fa-github"})
                    li1.append(icon1)
                    li1.append(" ")
                    a1 = soup.new_tag(
                        "a", href="https://github.com/phac-nml/HyRISE", target="_blank"
                    )
                    a1.string = "GitHub Repository"
                    li1.append(a1)
                    links_list.append(li1)

                    # Add to section
                    links_div.append(links_list)
                    about_section.append(links_div)

                    # Attribution to MultiQC (important)
                    attribution = soup.new_tag("p", **{"class": "small text-muted"})
                    attribution.string = "HyRISE is built using the MultiQC framework (Ewels P, et al. MultiQC: Summarize analysis results for multiple tools and samples in a single report. Bioinformatics. 2016;32(19):3047-8)."
                    about_section.append(attribution)

                    about_replaced = True
                    self.logger.info("Updated About section with proper attribution")

                # Strategy 2: Find by class or content
                if not about_replaced:
                    # Look for any section containing "About MultiQC"
                    for section in soup.find_all("section"):
                        header = section.find(["h3", "h4"])
                        if header and "About MultiQC" in header.get_text():
                            section.clear()

                            h4 = soup.new_tag("h4")
                            h4.string = "About HyRISE"
                            section.append(h4)

                            p1 = soup.new_tag("p")
                            p1.string = f"This report was generated using HyRISE v{self.version} (HIV Resistance Interpretation & Scoring Engine)."
                            section.append(p1)

                            p2 = soup.new_tag("p")
                            p2.string = "HyRISE provides comprehensive analysis of HIV drug resistance mutations, offering detailed visualizations and clinical interpretations to support treatment decisions."
                            section.append(p2)

                            # Attribution to MultiQC
                            attribution = soup.new_tag(
                                "p", **{"class": "small text-muted"}
                            )
                            attribution.string = "HyRISE is built using the MultiQC framework (Ewels P, et al. MultiQC: Summarize analysis results for multiple tools and samples in a single report. Bioinformatics. 2016;32(19):3047-8)."
                            section.append(attribution)

                            about_replaced = True
                            self.logger.info("Updated About section by content match")
                            break

                modifications["about_section"] = about_replaced
            except Exception as e:
                self.logger.error(f"Error updating About section: {str(e)}")

            # 10. UPDATE WELCOME SECTION
            try:
                welcome_replaced = False

                # Strategy 1: Find by ID or class
                welcome_selectors = [
                    "#mqc_welcome",
                    ".mqc-welcome",
                    "section.welcome",
                    "div.welcome",
                ]

                for selector in welcome_selectors:
                    welcome_elems = soup.select(selector)
                    for elem in welcome_elems:
                        elem.clear()

                        title = soup.new_tag("h3")
                        title.string = "HIV Resistance Analysis Report"
                        elem.append(title)

                        p1 = soup.new_tag("p")
                        p1.string = "This report provides a comprehensive analysis of HIV drug resistance mutations detected in your sample, with detailed visualizations and clinical interpretations to support treatment decisions."
                        elem.append(p1)

                        p2 = soup.new_tag("p")
                        p2.string = "Navigate through the sections using the menu on the left. Key sections include drug resistance profiles, mutation analyses, and clinical implications."
                        elem.append(p2)

                        welcome_replaced = True
                        self.logger.info(
                            f"Updated welcome section with selector: {selector}"
                        )
                        break

                # Strategy 2: Find introduction content
                if not welcome_replaced:
                    intro_section = None
                    # Find first main content section
                    main_content = soup.find(id="mainContent") or soup.find(
                        class_="mainpage"
                    )

                    if main_content:
                        # Look for a section with intro-like header
                        for section in main_content.find_all("section"):
                            header = section.find(["h1", "h2", "h3"])
                            if header and any(
                                word in header.get_text().lower()
                                for word in ["welcome", "introduction", "about"]
                            ):
                                intro_section = section
                                break

                        # If no section found, use first section
                        if not intro_section and main_content.find("section"):
                            intro_section = main_content.find_all("section")[0]

                        if intro_section:
                            intro_section.clear()

                            title = soup.new_tag("h3")
                            title.string = "HIV Resistance Analysis Report"
                            intro_section.append(title)

                            p1 = soup.new_tag("p")
                            p1.string = "This report provides a comprehensive analysis of HIV drug resistance mutations detected in your sample, with detailed visualizations and clinical interpretations to support treatment decisions."
                            intro_section.append(p1)

                            p2 = soup.new_tag("p")
                            p2.string = "Navigate through the sections using the menu on the left. Key sections include drug resistance profiles, mutation analyses, and clinical implications."
                            intro_section.append(p2)

                            welcome_replaced = True
                            self.logger.info(
                                "Created new welcome section in main content"
                            )

                modifications["welcome"] = welcome_replaced
            except Exception as e:
                self.logger.error(f"Error updating welcome section: {str(e)}")

            # 11. UPDATE CITATIONS SECTION
            try:
                citations_updated = False

                # Strategy 1: Find by ID
                citations = soup.find(id="mqc_citing")
                if citations:
                    # Replace with HyRISE citation
                    citations.clear()

                    title = soup.new_tag("h4")
                    title.string = "Citing HyRISE"
                    citations.append(title)

                    intro = soup.new_tag("p")
                    intro.string = "If you use HyRISE in your research, please cite:"
                    citations.append(intro)

                    citation_box = soup.new_tag("div", **{"class": "well"})

                    # HyRISE citation
                    p1 = soup.new_tag("p")
                    strong = soup.new_tag("strong")
                    strong.string = (
                        "HyRISE: HIV Resistance Interpretation & Scoring Engine"
                    )
                    p1.append(strong)
                    citation_box.append(p1)

                    p2 = soup.new_tag("p")
                    p2.string = "Osahan G, et al. National Microbiology Laboratory, Public Health Agency of Canada (2025)"
                    citation_box.append(p2)

                    p3 = soup.new_tag("p")
                    p3.string = "Available at: "
                    link = soup.new_tag("a", href="https://github.com/phac-nml/HyRISE")
                    link.string = "https://github.com/phac-nml/HyRISE"
                    p3.append(link)
                    citation_box.append(p3)

                    # MultiQC citation (important for attribution)
                    p4 = soup.new_tag("p", **{"class": "small text-muted"})
                    p4.string = "HyRISE is built using the MultiQC framework:"
                    citation_box.append(p4)

                    p5 = soup.new_tag("p", **{"class": "small text-muted"})
                    em = soup.new_tag("em")
                    em.string = "Ewels P, Magnusson M, Lundin S, Käller M. MultiQC: Summarize analysis results for multiple tools and samples in a single report. Bioinformatics. 2016;32(19):3047-8."
                    p5.append(em)
                    citation_box.append(p5)

                    citations.append(citation_box)
                    citations_updated = True
                    self.logger.info(
                        "Updated citations section with HyRISE and MultiQC citations"
                    )

                # Strategy 2: Find by content
                if not citations_updated:
                    # Look for any section containing "Citing MultiQC"
                    for section in soup.find_all("section"):
                        header = section.find(["h3", "h4"])
                        if (
                            header
                            and "Citing" in header.get_text()
                            and "MultiQC" in header.get_text()
                        ):
                            section.clear()

                            h4 = soup.new_tag("h4")
                            h4.string = "Citing HyRISE"
                            section.append(h4)

                            intro = soup.new_tag("p")
                            intro.string = (
                                "If you use HyRISE in your research, please cite:"
                            )
                            section.append(intro)

                            citation_box = soup.new_tag("div", **{"class": "well"})

                            # HyRISE citation
                            p1 = soup.new_tag("p")
                            strong = soup.new_tag("strong")
                            strong.string = (
                                "HyRISE: HIV Resistance Interpretation & Scoring Engine"
                            )
                            p1.append(strong)
                            citation_box.append(p1)

                            p2 = soup.new_tag("p")
                            p2.string = "Osahan G, et al. National Microbiology Laboratory, Public Health Agency of Canada (2025)"
                            citation_box.append(p2)

                            # MultiQC citation (important for attribution)
                            p4 = soup.new_tag("p", **{"class": "small text-muted"})
                            p4.string = "HyRISE is built using the MultiQC framework:"
                            citation_box.append(p4)

                            p5 = soup.new_tag("p", **{"class": "small text-muted"})
                            em = soup.new_tag("em")
                            em.string = "Ewels P, Magnusson M, Lundin S, Käller M. MultiQC: Summarize analysis results for multiple tools and samples in a single report. Bioinformatics. 2016;32(19):3047-8."
                            p5.append(em)
                            citation_box.append(p5)

                            section.append(citation_box)
                            citations_updated = True
                            self.logger.info(
                                "Updated citations section by content match"
                            )
                            break

                modifications["citations"] = citations_updated
            except Exception as e:
                self.logger.error(f"Error updating citations section: {str(e)}")

            # 12. UPDATE LINKS
            try:
                links_updated = False

                # Define link replacements
                link_replacements = {
                    "http://multiqc.info": "https://github.com/phac-nml/HyRISE",
                    "https://multiqc.info": "https://github.com/phac-nml/HyRISE",
                    "https://github.com/MultiQC/MultiQC": "https://github.com/phac-nml/HyRISE",
                    "https://github.com/ewels/MultiQC": "https://github.com/phac-nml/HyRISE",
                    "https://seqera.io": "https://www.canada.ca/en/public-health.html",
                }

                # Update all matching links
                for a_tag in soup.find_all("a", href=True):
                    original_href = a_tag["href"]

                    for old_url, new_url in link_replacements.items():
                        if old_url in original_href:
                            a_tag["href"] = original_href.replace(old_url, new_url)
                            links_updated = True

                            # Update link text if it contains MultiQC
                            if a_tag.string and "MultiQC" in a_tag.string:
                                a_tag.string = a_tag.string.replace("MultiQC", "HyRISE")

                if links_updated:
                    self.logger.info("Updated links to point to HyRISE resources")

                modifications["links"] = links_updated
            except Exception as e:
                self.logger.error(f"Error updating links: {str(e)}")

            # Write the updated HTML back to the file
            try:
                with open(html_path, "w", encoding="utf-8") as file:
                    file.write(str(soup))

                # Log successful modifications
                modified_items = [k for k, v in modifications.items() if v]
                self.logger.info(
                    f"HTML modifications completed successfully. Modified: {', '.join(modified_items)}"
                )

                return True, modifications
            except Exception as e:
                self.logger.error(f"Error writing modified HTML: {str(e)}")
                # Try to restore from backup
                try:
                    if os.path.exists(f"{html_path}.backup"):
                        shutil.copy2(f"{html_path}.backup", html_path)
                        self.logger.info("Restored HTML from backup after write error")
                except Exception:
                    self.logger.error("Failed to restore from backup")

                return False, {}

        except Exception as e:
            self.logger.error(f"Unexpected error in HTML modification: {str(e)}")
            import traceback

            self.logger.error(traceback.format_exc())
            return False, {}

    def post_process_report(
        self, logo_path: Optional[str] = None
    ) -> Tuple[bool, Dict[str, bool]]:
        """
        Post-process the MultiQC report to customize it for HyRISE.
        """
        # Look for possible report filenames
        possible_filenames = ["hyrise_resistance_report.html", "multiqc_report.html"]

        # Log all files in report directory for debugging
        try:
            report_files = os.listdir(self.report_dir)
            self.logger.info(f"Files in report directory: {report_files}")
        except Exception as e:
            self.logger.error(f"Error listing report directory: {str(e)}")

        # Find the first matching report file
        html_file = None
        for filename in possible_filenames:
            path = os.path.join(self.report_dir, filename)
            if os.path.exists(path):
                html_file = path
                self.logger.info(f"Found report file: {html_file}")
                break

        if not html_file:
            self.logger.error(
                f"Report HTML file not found. Checked: {possible_filenames}"
            )
            return False, {}

        try:
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
        except Exception as e:
            self.logger.error(f"Error in post_process_report: {str(e)}")
            import traceback

            self.logger.error(traceback.format_exc())
            return False, {}

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
        html_file = os.path.join(self.report_dir, "hyrise_resistance_report.html")
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
        "-v", "--version", default=__version__, help="HyRISE version number"
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

import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="hyrise",
    version="0.1.0",
    author="Gurasis Osahan",
    author_email="gurasis.osahan@phac-aspc.gc.ca",
    description="HIV Resistance Interpretation and Visualization System - A comprehensive tool for HIV drug resistance analysis and visualization",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/phac-nml/HyRISE",
    package_dir={"": "src"},
    include_package_data=True,
    package_data={"hyrise": ["hyrise.def", "HIVDB_9.8.xml"]},
    packages=setuptools.find_packages(where="src"),
    python_requires="<=3.11",
    install_requires=[
        "build>=1.2.2.post1",
        "packaging>=25.0",
        "wheel>=0.45.1",
        "poetry-core>=2.1.2",
        "pyproject-hooks>=1.2.0",
        "bio>=1.7.1",
        "biopython>=1.85",
        "pyyaml>=6.0.2",
        "numpy<2.0.0,>=1.24.3",
        "matplotlib>=3.10.1",
        "multiqc>=1.28",
        "requests>=2.32.3",
        "pip-tools>=7.4.1",
    ],
    entry_points={
        "console_scripts": [
            "hyrise=hyrise.cli:main",
            "hyrise-container-build=hyrise.commands.container:main",
            "hyrise-sierra=hyrise.commands.sierra:main",
        ]
    },
    keywords="hiv drug-resistance genomics bioinformatics visualization multiqc sierra hiv-sequence analysis mutation",
    license="GPL-3.0-or-later",
    project_urls={
        "Source": "https://github.com/phac-nml/HyRISE",
        "Tracker": "https://github.com/phac-nml/HyRISE/-/issues",
        "Documentation": "https://github.com/phac-nml/HyRISE/wiki",
        "Publication": "https://github.com/phac-nml/HyRISE#citation",
        "Contact": "https://github.com/phac-nml/HyRISE#contact",
    },
    classifiers=[
        "Development Status :: 4 - Beta",  # Changed from "1 - Beta" to standard "4 - Beta"
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Healthcare Industry",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Distributed Computing",
        "Operating System :: OS Independent",
        "Operating System :: POSIX :: Linux",
        "Natural Language :: English",
        "Environment :: Console",
        "Framework :: Pytest",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)

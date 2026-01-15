#!/usr/bin/env python3
"""
Setup script for estat-mcp-server
Provides backward compatibility with older pip versions
"""

from setuptools import setup, find_packages
import os

# Read README for long description
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

setup(
    name="estat-mcp-server",
    version="1.0.0",
    description="e-Stat Enhanced Analysis MCP Server with keyword suggestions",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="Yukihiro Yamashita",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/estat-mcp-server",
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        "requests>=2.28.0",
        "boto3>=1.26.0",
        "pandas>=1.5.0",
        "pyarrow>=10.0.0",
    ],
    extras_require={
        'dev': [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.990",
        ],
    },
    entry_points={
        'console_scripts': [
            'estat-mcp-server=estat_mcp_server.server:main',
        ],
    },
    python_requires='>=3.8',
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="mcp estat statistics data-analysis japan government-data",
    project_urls={
        "Documentation": "https://github.com/yourusername/estat-mcp-server#readme",
        "Source": "https://github.com/yourusername/estat-mcp-server",
        "Tracker": "https://github.com/yourusername/estat-mcp-server/issues",
    },
)

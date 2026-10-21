"""Package setup for logscope."""

from setuptools import setup, find_packages

setup(
    name="logscope",
    version="1.0.0",
    description="CLI tool for analysing application logs after incidents",
    python_requires=">=3.9",
    packages=find_packages(exclude=["tests*", "scripts*"]),
    entry_points={
        "console_scripts": [
            "logscope=logscope.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)

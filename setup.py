#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name="surveys",
    packages=find_packages(),
    include_package_data=True,
    build_requires=[
        "setuptools_scm",
    ],
    install_requires=[
        "flask>=2.0.0",
    ],
    entry_points={"console_scripts": ["surveys = surveys.__main__:main"]},
)

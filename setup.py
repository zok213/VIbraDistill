from setuptools import setup, find_packages

setup(
    name="vibradistill",
    version="2.0.0",
    description="Hardware-Faithful Edge AI and Streaming DSP for Bearing Fault Diagnosis & Prognostics",
    author="Team PORYGON",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "torch>=2.0.0",
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "pyyaml>=6.0",
    ],
)

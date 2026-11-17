#!/bin/bash#!/usr/bin/env bash
#
# This script is designed to address issues with installing specific libraries
# (such as numpy or scipy), which are dependencies of GridCal, on the Nord4 system.
#
# On Nord4, the provided Python environment is Intel-based. When attempting to run
# `pip install`, it tries to compile packages from source instead of using prebuilt wheels,
# leading to numerous build problems.
#
# The solution is to first install GridCal with the `--no-deps` flag to skip dependency installation.
# Then, by setting specific environment variables, we can force pip to use compatible binary wheels
# when installing GridCal's dependencies explicitly, avoiding source builds.


# Exit immediately on error, undefined var, or pipe failure
set -euo pipefail

# Load the specified Python module
module load python/3.10.2

# Define install target directory
TARGET_DIR="../packages"

# Ensure the directory exists, then clear it
mkdir -p "$TARGET_DIR"
rm -rf "${TARGET_DIR}/"*

# Install GridCalEngine without dependencies
python3 -m pip install --no-deps --target "$TARGET_DIR" GridCalEngine==5.3.40

# Install base requirements
python3 -m pip install --target "$TARGET_DIR" -r requirements.txt

# Set environment variables to force binary wheels and avoid Intel builds
export PIP_NO_BUILD_ISOLATION=no
export PIP_ONLY_BINARY=:all:

# Install GridCal-specific dependencies
python3 -m pip install --target "$TARGET_DIR" -r requirements_gridcal.txt

# Clean up environment variables
unset PIP_NO_BUILD_ISOLATION
unset PIP_ONLY_BINARY

# Clone stability analysis
git clone https://github.com/iraola/stability_analysis.git
cd stability_analysis
git checkout contingency_analysis_GC_api

echo "✅ Installation completed successfully into $TARGET_DIR"

#!/bin/bash

# Automatically update changelog with new version number
VERSION="$(./setup.py --version)"
dch -b -v "${VERSION}" "Automatic build"

# Build package ignoring the modified changelog
gbp buildpackage -us -uc --git-ignore-new

# Reset debian/changelog
git checkout debian/changelog

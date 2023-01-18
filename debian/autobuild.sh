#!/bin/bash

set -e

# Automatically update changelog with new version number as the deb package
# version will be what the latest entry in debian/changelog states
VERSION="$(./setup.py --version)"
# e.g. VERSION=2.2.3.dev5+gf11a1d0.d20230116
dch -b -v "${VERSION}" "Automatic build"

# Allowlist git to run inside container build directory if needed
git config --global --add safe.directory /build/rdiff-backup

# Build package ignoring the modified changelog
gbp buildpackage -us -uc --git-ignore-new

echo "
Debian build successful!

The rdiff-backup project has a git mirror configured at
https://code.launchpad.net/~rdiff-backup/rdiff-backup/+git/trunk

If you want it to trigger a build with build logs at
https://launchpad.net/~rdiff-backup/+archive/ubuntu/rdiff-backup-development/+builds?build_text=&build_state=all
and publish packages at
https://launchpad.net/~rdiff-backup/+archive/ubuntu/rdiff-backup-development
you need to have access to push to
https://github.com/rdiff-backup/rdiff-backup/tree/ubuntu-ppa
and have there a branch that is rebased on latest master, but has the Debian
version bumped in the debian/changelog file as Launchpad only triggers builds
if the version number is larger than what already exists in the PPA.

You can achieve that by running these commands after to local build passed:

git checkout -B ubuntu-ppa
git add debian/changelog
git commit -m 'Automatic build'
git push --force --verbose

# Move back to previous branch and reset debian/changelog
git checkout -
git checkout debian/changelog
"

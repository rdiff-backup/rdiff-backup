#!/bin/bash -x
# create a Python virtualenv to test rdiff-backup
VENV=${1:-dist/rdb}
mkdir -p $(dirname ${VENV})
python -m venv ${VENV}
python -m venv --upgrade --upgrade-deps ${VENV}
source ${VENV}/bin/activate
pip install -r requirements.txt

# this last command installs the currently developed version, repeat as needed!
pip install .

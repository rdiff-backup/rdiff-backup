#!/bin/bash -x
# create a Python virtualenv to test rdiff-backup
# Set the variable BINDEP to a profile to have also binary packages installed
# Possible profiles are: usage, devel
# e.g. BINDEP=devel ./create_venv.sh my/venv/dir

VENV=${1:-dist/rdb}
mkdir -p $(dirname ${VENV})
python -m venv ${VENV}
python -m venv --upgrade --upgrade-deps ${VENV}
source ${VENV}/bin/activate
if [[ -n "${BINDEP}" ]]
then  # install binary dependencies e.g. to compile rdiff-backup
	pip install bindep
	packages="$(bindep --brief ${BINDEP})"
	if [[ -n "${packages}" ]]
	then  # there are binary packages to install
		echo "NOTE:    sudo password and confirmation might be necessary"
		if [[ -n "$(which yum)" ]]
		then  # Fedora, RHEL, CentOS, etc
			sudo dnf install ${packages}
		elif [[ -n "$(which dnf)" ]]
		then  # Fedora, RHEL, CentOS (old)
			sudo yum install ${packages}
		elif [[ -n "$(which apt)" ]]
		then  # Debian, Ubuntu, etc
			sudo apt install ${packages}
		elif [[ -n "$(which zypper)" ]]
		then  # SuSE
			sudo zypper install ${packages}
		elif [[ -n "$(which pacman)" ]]
		then  # Arch, Manjaro, etc
			sudo pacman -S ${packages}
		fi
	fi
fi
pip install -r requirements.txt

# just for convenience
pip install powerline-status  # avoid warnings when using vim

# this last command installs the currently developed version, repeat as needed!
pip install .

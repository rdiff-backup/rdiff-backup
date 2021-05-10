BITS=$1
PYTHON_VERSION=$2
PYDIRECT=$3

if [[ ${BITS} == *32 ]] || [[ ${BITS} == *86 ]]
then
	bits=32
	lib_win_bits=Win32
	py_win_bits=win32
elif [[ ${BITS} == *64 ]]
then
	bits=64
	lib_win_bits=x64
	py_win_bits=win-amd64
else
	echo "ERROR: bits size must be 32 or 64, not '${BITS}'." >&2
	exit 1
fi

PYEXE=python.exe
if [[ -n ${PYDIRECT} ]]
then
	py_dir=C:/Python${bits}
	PYEXE=${py_dir}/${PYEXE}
fi

LIBRSYNC_DIR=${HOME}/librsync${bits}
export LIBRSYNC_DIR

ver_name=rdiff-backup-$(${PYEXE} setup.py --version)
py_ver_brief=${PYTHON_VERSION%.[0-9]}

# Extract the test files one directory higher
pushd ..
git clone https://github.com/rdiff-backup/rdiff-backup-filesrepo.git rdiff-backup-filesrepo
# ignore the one "Can not create hard link" error
7z x rdiff-backup-filesrepo/rdiff-backup_testfiles.tar || true
popd
# Then execute the necessary tests
${PYEXE} -m tox -c tox_win.ini -e py

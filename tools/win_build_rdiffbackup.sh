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
TOXEXE=tox.exe
if [[ -n ${PYDIRECT} ]]
then
	py_dir=C:/Python${bits}
	PYEXE=${py_dir}/${PYEXE}
	TOXEXE=${py_dir}/Scripts/${TOXEXE}
fi

LIBRSYNC_DIR=${HOME}/librsync${bits}
export LIBRSYNC_DIR

RDIFF_BACKUP_VERSION=rdiff-backup-$(${PYEXE} setup.py --version)-${bits}
export RDIFF_BACKUP_VERSION

${TOXEXE} -c tox_win.ini -e buildexe

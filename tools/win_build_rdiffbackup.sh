BITS=$1
PYTHON_VERSION=$2

if [[ "${BITS}" == *32 ]] || [[ "${BITS}" == x86 ]]
then
	bits=32
	lib_win_bits=Win32
	py_win_bits=win32
elif [[ "${BITS}" == *64 ]]
then
	bits=64
	lib_win_bits=x64
	py_win_bits=win-amd64
else
	echo "ERROR: bits size must be 32 or 64, not '${BITS}'." >&2
	exit 1
fi

LIBRSYNC_DIR=${HOME}/librsync${bits}
export LIBRSYNC_DIR

ver_name=rdiff-backup-$(python.exe setup.py --version)
py_ver_brief=${PYTHON_VERSION%.[0-9]}

python.exe setup.py bdist_wheel
PyInstaller.exe --onefile --distpath build/${ver_name}-${bits} \
	--paths=build/lib.win32-${py_ver_brief} \
	--console build/scripts-${py_ver_brief}/rdiff-backup \
	--add-data=src/rdiff_backup.egg-info/PKG-INFO\;rdiff_backup.egg-info

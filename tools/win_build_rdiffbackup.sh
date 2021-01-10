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
PYINST=PyInstaller.exe
if [[ -n ${PYDIRECT} ]]
then
	py_dir=C:/Python${bits}
	PYEXE=${py_dir}/${PYEXE}
	PYINST=${py_dir}/Scripts/${PYINST}
fi

LIBRSYNC_DIR=${HOME}/librsync${bits}
export LIBRSYNC_DIR

ver_name=rdiff-backup-$(${PYEXE} setup.py --version)
py_ver_brief=${PYTHON_VERSION%.[0-9]}

${PYEXE} setup.py bdist_wheel
${PYINST} --onefile --distpath build/${ver_name}-${bits} \
	--paths=build/lib.win32-${py_ver_brief} \
	--console build/scripts-${py_ver_brief}/rdiff-backup \
	--add-data=src/rdiff_backup.egg-info/PKG-INFO\;rdiff_backup.egg-info

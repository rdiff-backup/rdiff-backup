BITS=$1

if [[ ${BITS} -eq 32 ]]
then
	lib_win_bits=Win32
	py_win_bits=Win32
elif [[ ${BITS} -eq 64 ]]
then
	lib_win_bits=x64
	py_win_bits=win-amd64
else
	echo "ERROR: bits size must be 32 or 64, not '${BITS}'." >&2
	exit 1
fi
py_dir=C:/Python${BITS}

LIBRSYNC_DIR=${HOME}/librsync${BITS}
export LIBRSYNC_DIR

ver_name=rdiff-backup-$(${py_dir}/python.exe setup.py --version)
py_ver_brief=${PYTHON_VERSION%.[0-9]}

${py_dir}/python.exe setup.py bdist_wheel
${py_dir}/Scripts/PyInstaller.exe --onefile --distpath build/${ver_name}-${BITS} \
	--paths=build/lib.win32-${py_ver_brief} \
	--console build/scripts-${py_ver_brief}/rdiff-backup \
	--add-data=src/rdiff_backup.egg-info/PKG-INFO\;rdiff_backup.egg-info

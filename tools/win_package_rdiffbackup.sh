BITS=$1
PYDIRECT=$2

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

ver_name=rdiff-backup-$(${PYEXE} setup.py --version)

cp CHANGELOG.adoc COPYING README.adoc docs/*.adoc \
	build/${ver_name}-${bits}
pushd build
7z a -tzip ../dist/${ver_name}.win${bits}exe.zip ${ver_name}-${bits}
popd

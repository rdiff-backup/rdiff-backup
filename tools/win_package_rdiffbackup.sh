BITS=$1

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

ver_name=rdiff-backup-$(python.exe setup.py --version)

cp CHANGELOG.md COPYING README.md \
	docs/FAQ.md docs/examples.md docs/DEVELOP.md docs/Windows-README.md docs/Windows-DEVELOP.md \
	build/${ver_name}-${BITS}
pushd build
7z a -tzip ../dist/${ver_name}.${py_win_bits}exe.zip ${ver_name}-${BITS}
popd

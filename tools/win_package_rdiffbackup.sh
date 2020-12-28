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

ver_name=rdiff-backup-$(${py_dir}/python.exe setup.py --version)

cp CHANGELOG.md COPYING README.md \
	docs/FAQ.md docs/examples.md docs/DEVELOP.md docs/Windows-README.md docs/Windows-DEVELOP.md \
	build/${ver_name}-${BITS}
pushd build
7z a -tzip ../dist/${vername}.${py_win_bits}exe.zip ${vername}-${BITS}
popd

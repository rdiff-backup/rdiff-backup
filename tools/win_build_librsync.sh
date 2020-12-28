BITS=$1
LIBRSYNC_VERSION=$2  # actually the corresponding Git tag

if [[ ${BITS} -eq 32 ]]
then
	lib_win_bits=Win32
	py_win_bits=win32
elif [[ ${BITS} -eq 64 ]]
then
	lib_win_bits=x64
	py_win_bits=win-amd64
else
	echo "ERROR: bits size must be 32 or 64, not '${BITS}'." >&2
	exit 1
fi

LIBRSYNC_GIT_DIR=${HOME}/.librsync${BITS}
LIBRSYNC_DIR=${HOME}/librsync${BITS}
export LIBRSYNC_DIR

git clone -b ${LIBRSYNC_VERSION} https://github.com/librsync/librsync.git ${LIBRSYNC_GIT_DIR}

pushd ${LIBRSYNC_GIT_DIR}
cmake -DCMAKE_INSTALL_PREFIX=${LIBRSYNC_DIR} -A ${lib_win_bits} -DBUILD_SHARED_LIBS=OFF .
cmake --build . --config Release
cmake --install . --config Release
popd

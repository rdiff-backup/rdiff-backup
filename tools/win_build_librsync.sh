BITS=$1
LIBRSYNC_VERSION=$2  # actually the corresponding Git tag

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

LIBRSYNC_GIT_DIR=${HOME}/.librsync${bits}
LIBRSYNC_DIR=${HOME}/librsync${bits}
export LIBRSYNC_DIR

git clone -b ${LIBRSYNC_VERSION} https://github.com/librsync/librsync.git ${LIBRSYNC_GIT_DIR}

pushd ${LIBRSYNC_GIT_DIR}
cmake -DCMAKE_INSTALL_PREFIX=${LIBRSYNC_DIR} -A ${lib_win_bits} -DBUILD_SHARED_LIBS=TRUE -DBUILD_RDIFF=OFF .
cmake --build . --config Release
cmake --install . --config Release
popd

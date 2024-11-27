# script to test with specific verbosity and parameters
BASEDIR="$(dirname $0)"
TESTNAME="$(basename $0 .sh)"
export RDIFF_BACKUP_VERBOSITY=${1}
shift
python "${BASEDIR}/${TESTNAME}.py" "${@}"

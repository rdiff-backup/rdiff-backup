# Script to test with specific rdiff-backup verbosity and unittest parameters.
# It can be useful to temporarily debug a failing test script in the pipeline.
# Simply symlink this file (temporarily) to a shell script name aligned with
# the failing python test script and add it (temporarily) to the tox config.
# Example:
# 	ln -s whatever_test.sh testing/kill_test.sh  # aligned with kill_test.py
# 	sh testing/kill_test.sh 9 --failfast
# The first parameter is the _mandatory_ rdiff-backup verbosity
# The following parameters are optional unittest parameters

BASEDIR="$(dirname $0)"
TESTNAME="$(basename $0 .sh)"
export RDIFF_BACKUP_VERBOSITY=${1}
shift
python "${BASEDIR}/${TESTNAME}.py" "${@}"

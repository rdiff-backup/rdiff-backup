# script to test actions with heighten verbosity
BASEDIR="$(dirname $0)"
export RDIFF_BACKUP_VERBOSITY=${1}
shift
for script in ${BASEDIR}/action_*_test.py
do
	coverage run ${script} "${@}"
done

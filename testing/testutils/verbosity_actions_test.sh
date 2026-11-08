# script to test actions with heighten verbosity
BASEDIR="$(dirname $0)"
BASEDIR="${BASEDIR%/testutils}"
export RDIFF_BACKUP_VERBOSITY=${1}
shift
pytest --cov-append --cov=rdiff_backup --cov=rdiffbackup \
	${BASEDIR}/action_*_test.py

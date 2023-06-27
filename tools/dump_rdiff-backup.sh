#!/bin/sh
# call with the name of the rdiff-backup repository to analyze

if [ -z "$1" ]
then
	echo "Call $0 <reponame>" >&2
	exit 1
fi

REPOPATH="${1}"
REPONAME=$(basename "${REPOPATH}")

OUT_FILE="${TMPDIR:-/tmp}/${REPONAME}"
HTML_FILE="${OUT_FILE}.html"
JSON_FILE="${OUT_FILE}.json"

tree -CH "${REPONAME}" --nolinks \
	-apugsD --timefmt='%Y-%M-%d/%T' --inodes --device --dirsfirst \
	"${REPOPATH}" -o "${HTML_FILE}"
tree -J \
	-apugsD --timefmt='%s' --inodes --device --dirsfirst \
	"${REPOPATH}" -o "${JSON_FILE}"

gzip --verbose --force "${HTML_FILE}" "${JSON_FILE}"

echo "Attach '${HTML_FILE}.gz' and '${JSON_FILE}.gz' to your GitHub issue"

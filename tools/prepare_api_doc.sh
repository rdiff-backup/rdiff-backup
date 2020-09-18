#!/bin/sh
# this function gathers all calls going through the client/server connection.
# the result can only be used as a basis or validation for the actual API
# documentation, especially because it can't make the difference between
# internal and external methods.

if ! [ -n "$1" ]
then
	echo "Usage: $0 XYY" >&2
	exit 1
fi

API_FILE=docs/api/v${1}.md

echo -e "\n## Sources\n" > ${API_FILE}.src

echo -e "\n### Internal\n" >> ${API_FILE}.src

grep -ro -e 'conn\.[a-zA-Z0-9._]*' src | \
	awk -F:conn. '{print "* `" $2 "`"}' | sort -u >> ${API_FILE}.src

echo -e "\n### External\n" >> ${API_FILE}.src


echo -e "\n## Testing\n" > ${API_FILE}.testing

echo -e "\n### Internal\n" >> ${API_FILE}.testing
echo -e "\n### External\n" >> ${API_FILE}.testing

grep -ro -e 'conn\.[a-zA-Z0-9._]*' testing | \
	awk -F:conn. '{print "* `" $2 "`"}' | sort -u | \
	grep --fixed-strings --line-regexp --file ${API_FILE}.src \
		--invert-match >> ${API_FILE}.testing

echo -e "# rdiff-backup API description v${1}\n" > ${API_FILE}
echo -e "\n## Format\n" >> ${API_FILE}

cat ${API_FILE}.* >> ${API_FILE}

rm ${API_FILE}.*

echo "API description prepared at '${API_FILE}'."

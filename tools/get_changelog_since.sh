#!/bin/bash
# get a list of changes and authors since a given revision tag in Git
# outputs changes marked with 'XYZ:' and a unique list of authors
# if no tag is given, uses the latest valid one

if [[ -z "${1}" ]]
then
	RELTAG=$(git tag | grep '^v' | sort --version-sort | tail -n1)
	echo "Listing changes since ${RELTAG}" >&2
else
	RELTAG="${1}"
fi

echo "(make sure the version is the next correct one)" >&2
echo
echo "== New in v$($(dirname $0)/../setup.py --version) ($(date -I))"

echo -e "\n=== Changes\n"
git log ${RELTAG}.. |
	sed -n '/^ *[A-Z][A-Z][A-Z]: / s/^ */* /p' | sort \
	| fold -w 72 -s | sed 's/^\([^*]\)/       \1/'

echo -e "\n=== Authors\n"
git log ${RELTAG}.. |
	awk -F': *| *<' '$1 == "Author" { print "* " $2 }' | sort -u

echo

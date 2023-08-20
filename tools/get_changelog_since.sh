#!/bin/bash
# get a list of changes and authors since a given revision tag in Git
# outputs changes marked with 'XYZ:' and a unique list of authors
# if no tag is given, uses the latest valid one

# Letter used by Asciidoc to mark headers
H='='

function usage() {
        local exit_code=${1:-0}
        echo "Usage: $0 [-h] [-m] [latest Git tag]"
        echo "       -h - output usage and exit"
        echo "       -M - output in Markdown format (Asciidoc is default)"
        echo "       a Git tag since which to list changes"
        exit ${exit_code}
}

# parse the parameters

while getopts hM opt
do
        case "${opt}" in
        h)
                usage 0
                ;;
        M)
                H='#'
                ;;
        ?)
                echo "Unknown option" >&2
                usage 1
                ;;
        esac
done

shift $((OPTIND - 1))

if [[ -z "${1}" ]]
then
	RELTAG=$(git tag | grep '^v' | sort --version-sort | tail -n1)
	echo "Listing changes since ${RELTAG}" >&2
else
	RELTAG="${1}"
fi

echo "(make sure the version is the next correct one)" >&2
echo
echo "${H}${H} New in v$($(dirname $0)/../setup.py --version) ($(date -I))"

echo -e "\n${H}${H}${H} Changes\n"
git log ${RELTAG}.. |
	sed -n '/^ *[A-Z][A-Z][A-Z]: / s/^ */* /p' | sort \
	| fold -w 72 -s | sed 's/^\([^*]\)/       \1/'

echo -e "\n${H}${H}${H} Authors\n"
git log ${RELTAG}.. |
	awk -F': *| *<' '$1 == "Author" { print "* " $2 }' | sort -u

echo

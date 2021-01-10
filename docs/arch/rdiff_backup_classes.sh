#!/bin/sh -x
# script to document classes from Python sources

BASE_DIR=$(dirname $0)/../../src
PUML_FILE=$(realpath ${0%.sh}.puml)

cd ${BASE_DIR}
grep -r --include \*.py ^class | sort | awk -F'[:()]*' '
        BEGIN {
                print "@startuml"
        }
        {
                gsub(".py$", "", $1)
                gsub("^.*/", "", $1)
                gsub("^class *", "", $2)
                if ($1 != package) {
                        if (package) { print "}" }
                        package = $1
                        print "package " package " {"
                }
		if ($3 == "Exception" || $2 == "Exception" || $2 ~ /Error$/) {
			print "	class " $2 " << (E,#FF7700) Exception >>"
		} else {
			print "	class " $2
		}
		# the Exception descendence is marked by coloring not by arrows
                if ($3 && $3 != "Exception") print "	" $3 " <|-- " $2
        }
        END {
                if (package) print "}"
                print "@enduml"
        }' > ${PUML_FILE}

plantuml -tsvg ${PUML_FILE}

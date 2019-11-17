#!/bin/sh
# A rather stupid script to generate graphics from the rdiff-backup code structure
# you'll need to install plantuml from https://plantuml.com/ to generate them.
# Do NOT wonder, the graphics are huge and difficult to oversee.

CODE_DIR=$(dirname $0)/../../src/rdiff_backup
BUILD_DIR=${1:-$(dirname $0)/../../build}

mkdir -p "${BUILD_DIR}"


# generate an overview of class definitions and their hierarchy

awk -F'[ ():]' '
BEGIN { print "@startuml" }
$1 == "class" {
        if (FILENAME != pkg) {
                if (pkg) print "}"
		print "'\''", FILENAME
		fields = split(FILENAME, pkgs, "/")
		sub(".py","",pkgs[fields])
                print "package",pkgs[fields],"{"
                pkg = FILENAME
        }
        if ($3) {
		if ($3 == "Exception") {
			print "\t" "class",$2,"<<(E,Red) Exception>>"
		} else {
			print "\t" $3,"<|--",$2
		}
        } else {
                print "\t" "class",$2
        }
}
END {
        if (pkg) print "}"
        print "@enduml"
}' ${CODE_DIR}/*.py > ${BUILD_DIR}/rdiff-backup-classes.plantuml
PLANTUML_LIMIT_SIZE=16384 plantuml ${BUILD_DIR}/rdiff-backup-classes.plantuml


# generate an overview of the imports within the src/rdiff_backup modules

awk -F' *import *|, *' '
BEGIN { print "@startuml" }
$1 == "from ." && $0 !~ /^#/ {
        if (FILENAME != pkg) {
		print "'\''", FILENAME
		fields = split(FILENAME, pkgs, "/")
		module = pkgs[fields]
		sub(".py","",module)
                pkg = FILENAME
        }
	sub(" *#.*$","")  # remove comments from line
	sub("^ *from . import *","")  # remove import command
	eol = $NF
	do {
		sub("^ *","")  # remove beginng blanks
		if ( $NF !~ /[a-z]/ ) last = NF - 1
		else last = NF
		if ( $NF == "(" ) field = last + 1
		else field = 1
		while (field <= last) {
			# the following looks useless but we can be more flexible
			if ( $field ~ /^[A-Z]/ ) print $field,"o--",module
			else print $field,"o--",module
			field++
		}
		getline
		sub(" *#.*$","")  # remove comments from line
	} while ((eol == "\\" && $NF == "\\") || (eol == "(" && $NF != ")"))
}
END {
        print "@enduml"
}' ${CODE_DIR}/*.py > ${BUILD_DIR}/rdiff-backup-imports.plantuml
PLANTUML_LIMIT_SIZE=16384 plantuml ${BUILD_DIR}/rdiff-backup-imports.plantuml

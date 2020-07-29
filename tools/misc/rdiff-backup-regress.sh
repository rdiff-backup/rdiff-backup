#!/bin/bash
THIS=`basename $0`
VERSION="1.0 [25 Aug 2016]"
COLUMNS=$(stty size 2>/dev/null||echo 80); COLUMNS=${COLUMNS##* }
ITERATIONS=1
while getopts ":dfhln:qw" optname; do
  case "$optname" in
    "d")	DEBUG="y";;
    "f")	FORCE="y";;
    "h")	HELP="y";;
    "l")	CHANGELOG="y";;
    "q")	QUIET="y"; RDIFFBACKUPOPTIONS="--terminal-verbosity 0";;
    "n")	ITERATIONS=$OPTARG;;
    "w")	COLUMNS=30000;; #suppress line-breaks for help
    "?")	echo "Unknown option $OPTARG"; exit 1;;
    ":")	echo "No argument value for option $OPTARG"; exit 1;;
    *)		# Should not occur
		echo "Unknown error while processing options"; exit 1;;
  esac
done
shift $(($OPTIND-1))
if [ -z "$QUIET" -o -n "$HELP$CHANGELOG" -o -z "$1" ]; then
	echo -en "\n$THIS v$VERSION by Dominic"
	[ -z "$HELP" -a -n "$1" ] && echo -n " (-h for help)"
	echo -e "\n${THIS//?/=}\n"
fi
if [ -n "$HELP" -o -z "$1$CHANGELOG" ]; then
	echo -e "Regresses an rdiff-backup archive by one or more backup \
sessions i.e. to the state it was in before the last n backup sessions.

$THIS can be used to remove an unwanted recent backup run \
- for instance one that excludes a lot of the usual data or includes a lot \
of extraneous data. Because rdiff-backup saves a full history of data via \
incremental diff (delta) files, \
excluding or including a lot of data on one occasion and then correcting \
it the next time will bloat your repository/archive substantially (by twice \
the compressed size of the relevant data). By using $THIS to regress the \
archive back to the point before the incorrect backup, you can undo this \
and recover the lost space. You can consider it a workaround for a \
missing --regress option in rdiff-backup.

If the session (aka run or increment) you want to remove is not the most \
recent then you can use the -n option to remove the requisite number of \
sessions from the most recent up to the one you want to \
remove - it is not possible to remove just one session from the middle \
of an archive. If you want to remove some of the earliest, rather than the \
most recent, sessions you \
should instead use rdiff-backup with --remove-older-than option.

$THIS can also be used with a corrupted archive if regression \
does not happen automatically and cannot be initiated with \
--check-destination-dir; however this may not \
be successful, and could make things worse, so you are advised \
to take a backup of the entire repository first.

$THIS works by 'tricking' rdiff-backup into thinking that the last backup is \
faulty (by creating a second current_mirror file), and then \
runs rdiff-backup --check-destination-dir to perform the regression. With -n \
option it just repeats this operation a number of times. \
The methodology was originally suggested by Janne Peltonen - kudos.

Note that regressions can take a long time; don't take any other actions \
on the archive until $THIS has completed.

Health Warnings: $THIS removes one or more recent backups sessions from your \
rdiff-backup archive. Once removed, a backup session is irrecoverable. \
Earlier sessions in the same archive should still be recoverable.

If $THIS is run with superuser permissions (e.g. sudo), and the original \
archives were created by a different user then after recovery some file \
ownerships may have changed. You are advised if possible to run $THIS as the \
same user who originally created and updated the rdiff-backup archive that is \
being regressed.

Usage:\t$THIS [options] archive-path
Note that, unlike rdiff-backup, $THIS must be run on the machine hosting the \
repository, or (untested) via NFS mount.

Example:
    ./$THIS -n 2 /home/fred/backup

Options:\t-f - Force, proceed with no prompt
\t\t-h - Show this help text and then quit
\t\t-l - Show changelog and then quit
\t\t-n num - Regress the backup recursively num times (where num is an integer) - default 1
\t\t-q - Quiet, no output unless an error occurs

Dependencies: awk bash coreutils rdiff-backup sed

License: Copyright © 2016 Dominic Raferd. Licensed under the Apache License, \
Version 2.0 (the \"License\"); you may not use this file except in compliance \
with the License. You may obtain a copy of the License at \
https://www.apache.org/licenses/LICENSE-2.0. Unless required by applicable \
law or agreed to in writing, software distributed under the License is \
distributed on an \"AS IS\" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY \
KIND, either express or implied. See the License for the specific language \
governing permissions and limitations under the License.
"|fold -s -w $COLUMNS
fi
if [ -n "$CHANGELOG" ]; then
	[ -n "$HELP" ] && echo "Changelog:"
	echo "\
1.0 [25 Aug 2016] - updated help info
0.9 [12 Aug 2016] - improved user comparison
0.8 [23 Sep 2015] - don't descend directories searching for current_mirror(s)
0.7 [09 Dec 2014] - update help and warn if running as superuser
0.6 [22 Jan 2014] - minor text output fixes
0.5 [16 Dec 2013] - help text updated
0.4 [29 Jul 2013] - help text updated, added changelog
"|fold -s -w $COLUMNS
fi
[ -n "$HELP$CHANGELOG" ] && exit
if [ ! -d "$1" ]; then
	echo "Cannot find directory \"$1\", aborting..."
	exit 1
fi
ARCHIVE=$1
if [ ! -d "$ARCHIVE/rdiff-backup-data/increments" ]; then
	echo "$ARCHIVE does not appear to contain a valid rdiff-backup archive, aborting..."
	exit 1
fi
REQOWNER=`ls -dl "$ARCHIVE/rdiff-backup-data/increments"|awk '{print $3}'`
if [[ $(id -un) != $REQOWNER ]]; then
	[[ $(id -u) == 0 ]] || { echo "You must be user '$REQOWNER' or, less advisedly, superuser (root) for this operation, aborting" >&2; exit 1; }
	echo -e "You are user '$(id -un)', not '$REQOWNER', which may result in changed ownership of some files."
	read -t 30 -p "Are you sure you wish to continue (y/-)? "
	[ "$REPLY" != "y" ] && echo "Exiting, no changes made" && exit 0
fi
REQOWNER=`ls -dl "$ARCHIVE/rdiff-backup-data/increments"|awk '{print $3":"$4}'`


[ -z "$QUIET" ] && echo -e "Using repository: $ARCHIVE\nStarted `date`"
for ((ITERATION=1; ITERATION<=$ITERATIONS; ITERATION++)); do
	WHENLAST=$(find "$ARCHIVE/rdiff-backup-data" -maxdepth 1 -name "current_mirror*"|sed 's/.*current_mirror\.\([^.]*\).*/\1/')
	NUMCURRENT=`echo $WHENLAST|awk '{print NF}'`
	if [ $NUMCURRENT -ne 2 ]; then
		if [ $NUMCURRENT -ne 1 ]; then
			echo "$NUMCURRENT current_mirror files, aborting..."
			exit 1
		else
			[ -z "$QUIET" ] && echo "Note: rdiff-backup does not recognise this archive as damaged"
		fi
	else
		[ -z "$QUIET" -a $ITERATION -eq 1 ] && echo "Note: rdiff-backup recognises this archive as damaged"
		WHENLAST=$(echo "$WHENLAST"|awk '{print $1}')
	fi
	PREVRUN=`ls $ARCHIVE/rdiff-backup-data/mirror_metadata*|tail -n2|head -n1|sed 's/.*mirror_metadata\.\([^.]*\).*/\1/'`
	if [ -z "$FORCE" -a $ITERATION -eq  1 ]; then
		[ $ITERATIONS -gt 1 ] && echo -n "Regression 1/$ITERATIONS: "
		read -n 1 -t 30 -p "About to regress $ARCHIVE archive from $WHENLAST to $PREVRUN: ok (y/-)? "
		[ "$REPLY" != "y" ] && echo " - aborting..." && exit 1
		echo
	fi
	if [ $NUMCURRENT -eq 1 ]; then
		cp -a "$ARCHIVE/rdiff-backup-data/current_mirror.$WHENLAST.data" "$ARCHIVE/rdiff-backup-data/current_mirror.$PREVRUN.data"
		[ -n "$DEBUG" ] && echo "Copied current_mirror"
	fi
	[ -z "$QUIET" ] && echo "Regression $ITERATION of $ITERATIONS: from $WHENLAST to $PREVRUN..."
	rdiff-backup $RDIFFBACKUPOPTIONS --check-destination-dir $ARCHIVE
	RUNERR=$?
	[ -z "$QUIET" -a $RUNERR -eq 0 ] && echo -e "Most recent backup is now $PREVRUN\nRegression $ITERATION of $ITERATIONS completed successfully" || echo "Error $RUNERR occurred when attempting to regress archive...">&2
	THISOWNER=`ls -l "$ARCHIVE/rdiff-backup-data/mirror_metadata.$PREVRUN.snapshot.gz"|awk '{print $3":"$4}'`
	if [ "$THISOWNER" != "$REQOWNER" ]; then
		if [ -f "$ARCHIVE/rdiff-backup-data/mirror_metadata.$PREVRUN.snapshot.gz" ]; then
			[ -z "$QUIET" ] && echo -n "Correcting ownership of a key file (1) to $REQOWNER: "
			chown $REQOWNER "$ARCHIVE/rdiff-backup-data/mirror_metadata.$PREVRUN.snapshot.gz"
			[ $? -eq 0 ] && echo "[OK]" || echo "[FAIL]"
		fi
		if [ -f "$ARCHIVE/rdiff-backup-data/current_mirror.$PREVRUN.data" ]; then
			[ -z "$QUIET" ] && echo -n "Correcting ownership of a key file (2) to $REQOWNER: "
			chown $REQOWNER "$ARCHIVE/rdiff-backup-data/current_mirror.$PREVRUN.data"
			[ $? -eq 0 ] && echo "[OK]" || echo "[FAIL]"
		fi
	fi
	if [ $RUNERR -gt 0 -a $ITERATION -lt $ITERATIONS ]; then
		echo "Further regressions aborted because of error">&2
		break
	fi
done
[ -z "$QUIET" ] && echo "Ended `date`"

#!/bin/bash
# Clean out the "zero-diff" increment files and adjust the file_statistics
# file to match.
#
# Author: Robert Nichols
# License: Released to Public Domain, 2022-02-27
# Warranty: None. Has not, as yet, been known to eat any babies.
#
# Look in a file_statistics file for files that have a change flagged
# and a non-zero increment size.  For each of those files, examine the
# changes in the mirror_metadata file.  If there are no changes except
# possibly to NumHardLinks, Inode, and DeviceLoc, then the change flag
# and change size can be zeroed in file_statistics and the "zero-diff"
# file can be removed from the increments.
#
# The file_statistics file is never actually read by rdiff-backup, so
# the cleanup in that file is just for the rdiff-backup-statistics
# report..

export LC_ALL=C
Merge=/root/rback/metamerge.awk
Cmd="${0##*/}"
CmdDir=${0%$Cmd}
case "$CmdDir" in
"") CmdDir="$PWD";;
/*) CmdDir="${CmdDir%/}";;
*)  CmdDir="$PWD/${CmdDir%/}";;
esac

function usage() {
    echo "Usage: $Cmd -[ynFdD] [-Q N_parallel] statistics_file [statistics_file ...]"
    echo "       $Cmd -[ynFdD] [-Q N_parallel] -i range archive_directory [archive_directory ...]"
    [ -n "$1" ] && exit $1
}

function err_exit() {
    echo "ERROR [$Cmd]: $1" >&2
    exit 1
}

Prompt=y
Paranoia=y
Nparallel=1
unset Debug Which StatFile
while getopts ynDdFi:Q: Arg; do
    case "$Arg" in
    y)  Prompt=n;;
    n)  Prompt=N;;
    d)  [ "$Debug" != y ] && Debug=x	# Save unless nothing found
	[ -z "$TMPDIR" ] && export TMPDIR=/var/tmp;;
    D)  Debug=y				# Save always
	[ -z "$TMPDIR" ] && export TMPDIR=/var/tmp;;
    F)  Paranoia=n;;
    i)  Which="$OPTARG"
	if [[ $Which =~ ^([0-9]+):([0-9]+) ]]; then
	    First=${BASH_REMATCH[1]}
	    Last=${BASH_REMATCH[2]}
	elif [[ $Which =~ ^([0-9]+):$ ]]; then
	    First=${BASH_REMATCH[1]}
	    Last=99999
	elif [[ $Which =~ ^[0-9]+ ]]; then
	    First=$Which
	    Last=$First
	else
	    First=-1; Last=-1
	fi
	if [ $First -lt 0 -o $Last -lt $First ]; then
	    echo "[$Cmd]: Illegal range: \"$Which\"" >&2
	    exit 1
	fi;;
    Q)  Nparallel=$OPTARG;;
    *)  usage 1;;
    esac
done
shift $((OPTIND-1))
[ $? != 0 -o $# -lt 1 ] && { usage; exit 1; }
if [ $Nparallel -gt 1 -a $Prompt = y ]; then
    echo "[$Cmd]: Parallel checks must be run with \"-n\" or \"-y\"" >&2
    exit 1
fi

shopt -s extglob
function openFD() {
    # Open compressed or uncompressed version of a file on the given
    # file descriptor and translate octal escapes "\134" (backslash) and
    # "\012" (newline) translate to the 2-character sequences "\\" and
    # "\n". All other translated characters are represented literally.
    Out="$Tmpdir/$(basename "$2")"
    if [[ -f "$2.gz" ]]; then
	if [[ "$3" = xread ]]; then
	    gunzip -fc <"$2.gz" | \
		while read -r Str; do printf '%b\n' "$Str"; done | \
		sed -e 's/\\/&&/g' -e 's/\n/\\n/g' >"$Out"
	else
	    gunzip -fc <"$2.gz" >"$Out"
	fi
    elif [[ -s "$2" ]]; then
	if [[ "$3" = xread ]]; then
	    while read -r Str; do printf '%b\n' "$Str"; done <"$2" | \
		sed -e 's/\\/&&/g' -e 's/\n/\\n/g' >"$Out"
	else
	    Out="$2"
	fi
    else
	return 1
    fi
    eval "exec $1<\"$Out\""
}

shopt -s extglob
if [ -n "$Which" ]; then
    Nstats=0
    for Arg in "$@"; do
	[ $# -gt 1 ] && echo ":: ${Arg%/rdiff-backup-data/*} ::"
	Incs=($(find "$Arg/rdiff-backup-data" -maxdepth 1 \
	    \( -name 'file_statistics.*.data.gz' -o -name 'file_statistics.*.data' \) \
	    -printf '%p\n' | sort -r))
	[ ${#Incs[*]} -gt 0 ] || usage 1
	if [ $First -ge ${#Incs[*]} ]; then
	    err_exit "Invalid start: $First (available: {0..$((${#Incs[*]}-1))})"
	fi
	for ((N=First; N<=Last && N<${#Incs[*]}; ++N)); do
	    StatList[$((Nstats++))]="${Incs[N]}"
	done
    done
else	# Args must be a file_statistics files in the rdiff-backup-data directories
    StatList=("$@")
fi

# Extract the longest common path prefix, cd to that directory, and
# strip the common prefix from the list members
Common="${StatList[0]%/*}/"
case "$Common" in
/*) ;;
*)  Common="./$Common";;
esac
until [[ "$Common" =~ ^\./$ ]]; do
    for ((N=1; N<${#StatList[*]}; ++N)); do
	[[ "${StatList[$N]}" =~ ^"${Common#./}" ]] || break
    done
    [ $N -ge ${#StatList[*]} ] && break
    Common="${Common%/*/}/"
done
Common="${Common#./}"
cd "$Common" || exit 1
for ((N=0; N<${#StatList[*]}; ++N)); do
    StatList[$N]="${StatList[$N]#$Common}"
done
unset Incs

#####
# Process statistics files. If more than one file is being processed in
# parallel, this MUST be run in a subprocess for each set or the variables
# and file descriptors will collide.  A mark number and increment can
# optionally be provided with a "-m" flag to tag messages from parallel
# threads.
# Arguments are file_statistics files in the rdiff-backup-data directory of
# an archive. The files need not all be in the same directory.
# 
# Note: The ability to have multiple arguments and a mark increment is not
#       currently used by the calling program.
#####
function procfile() {
    unset MarkN Mark
    if [ "$1" = -m ]; then
	MarkN=${2%,*}
	MarkInc=${2#*,}
	shift 2
    fi
    Basedir="$PWD"
    for Arg in "$@"; do
	cd "$Basedir"
	[[ ! "$Arg" =~ / ]] || cd ${Arg%/*} || return 4
	if [ -n "$MarkN" ]; then
	    Mark="[$MarkN] "
	    ((MarkN += MarkInc))
	fi
	Sys="$(/bin/pwd)"
	Sys="${Sys%/*}"
	Sys="${Sys##*/}"
	StatFile=${Arg##*/}
	CurTime=${StatFile#file_statistics.}
	CurTime=${CurTime%.gz}
	CurTime=${CurTime%.data}
	shopt -s extglob
	Mirrors=(mirror_metadata*.@(diff|snapshot)?(.gz))
	shopt -u extglob
	for ((Index=${#Mirrors[*]}-1; Index >= 0; --Index)); do
	    [[ "${Mirrors[$Index]}" =~ ^mirror_metadata.$CurTime ]] && break
	done
	if (( $Index < 0 )); then
	    echo "ERROR [$Cmd]: No mirror_metadata found for $StatFile" >&2
	    return 1
	fi
	if (( $Index == 0 )); then
	    echo "[$Cmd]: $Mark$CurTime has no prior session." >&2
	    continue
	fi
	Meta_0=${Mirrors[$Index]}
	Meta_1=${Mirrors[$Index-1]}
	Extended_0=extended_attributes.$CurTime.snapshot
	Extended_1=extended_attributes.${Meta_1#mirror_metadata.}
	Extended_1=${Extended_1%.gz}
	Extended_1=${Extended_1/diff/snapshot}
	Access_0=access_control_lists.$CurTime.snapshot
	Access_1=access_control_lists.${Meta_1#mirror_metadata.}
	Access_1=${Access_1%.gz}
	Access_1=${Access_1/diff/snapshot}

	Tmpdir=$(mktemp -d --tmpdir deldiffs.XXXXXX) || return 1
	if [ "$Debug" = y ]; then
	    echo "${Mark}Tmpdir \`$Tmpdir' will not be removed" >&2
	else
	    trap "rm -r \"$Tmpdir\"" 0
	fi

# If necessary, reconstruct Meta_0 from later snapshot
	for ((N=Index; N<${#Mirrors[*]}; ++N)); do
	    [[ "${Mirrors[$N]}" =~ \.snapshot(\.gz)? ]] && break
	done
	if (( $N >= ${#Mirrors[*]} )); then
	    "ERROR [$Cmd]: No snapshot found to construct $Meta_0"
	    return 1
	fi
	if (( $N > $Index )); then
	    Old="$Tmpdir/${Mirrors[N]%.gz}"
	    gunzip -fc <${Mirrors[N]} >"$Old"
	    while (( --N >= Index )); do
		New="$Tmpdir/${Mirrors[N]%.diff*}"
		awk -f "$Merge" $Old <(gunzip -fc <${Mirrors[N]}) >"$New"
		rm "$Old"
		Old="$New"
	    done
	    Meta_0="$New"
	fi

	Suffix=${Meta_1#**mirror_metadata.}
	Suffix=${Suffix%.gz}
	Suffix=${Suffix/.snapshot/.diff}
	echo "${Mark}Processing $Sys $CurTime => ${Suffix%.diff}" >&2

#####
# Just open these files once so that subsequent reads will continue
# from the current position.
#   fd3, fd4: current and prior mirror_metadata files
#   fd5, fd6: current and prior extended_attributes files
#   fd7, fd8: current and prior access_control_lists files
#
# Note: fd9 is used for the dispatcher fifo
#####
	if [[ "$Meta_0" =~ \.gz$ ]]; then
	    exec 3< <(gunzip -fc "$Meta_0")
	else
	    exec 3< "$Meta_0"
	fi
	exec 4< <(gunzip -fc "$Meta_1")
	openFD 5 "$Extended_0" || unset Extended_0
	openFD 6 "$Extended_1" || unset Extended_1
	openFD 7 "$Access_0" || unset Access_0
	openFD 8 "$Access_1" || unset Access_1

# Create the script that passes variables to awk.
	cat >$Tmpdir/initvars.awk <<EOF
function initvars() {
# $(dirname $PWD)
    Cmd = "$Cmd"
    Mark = "${Mark% }"
    newstats = "$Tmpdir/newstats"
    Paranoia = "$Paranoia"
    missdiff = "$Tmpdir/missdiff"
    Meta_0 = "$Meta_0"
    Meta_1 = "$Meta_1"
    Extend_0 = "$Extended_0"
    Extend_1 = "$Extended_1"
    Access_0 = "$Access_0"
    Access_1 = "$Access_1"
}
EOF
	:
	# If the original statistics file has NUL separators, then
	# so should the new one.
	NULsep=$(($(gunzip -f <${StatFile##*/} 2>/dev/null | head -c 4096 | wc -l) < 2))

	awk --re-interval -f "$Tmpdir/initvars.awk" -f "$CmdDir/deldiffs.awk" \
	    < <(gunzip -f <${StatFile##*/} | tr '\0' '\n') \
	    >"$Tmpdir/rmlist"
	Rc=$?
	if [ $Rc = 10 ]; then		# No zero-diff cases found
	    if [ "$Debug" != y ]; then
		rm -r "$Tmpdir"
		trap "" 0
		continue
	    fi
	elif [ "$Debug" = x ]; then
	    echo "${Mark}Tmpdir \`$Tmpdir' will not be removed" >&2
	    trap "" 0
	fi
	[ $Rc = 0 ] || return 1		# Error from awk script

	if [[ "$Prompt" = N ]]; then
	    if [ -z "$Debug" ]; then
		rm -r "$Tmpdir"
		trap "" 0
	    fi
	else
	    if [[ "$Prompt" = n ]]; then
		REPLY=y
	    else
		read -p "OK? "
	    fi
	    if [[ "$REPLY" =~ ^[yY] ]]; then
		case "$Debug" in
		x|y)
		    Action=(tar -uf "$Tmpdir/diff_files.tar" --remove-files);;
		*)  Action=(rm);;
		esac
		while read -r Name; do
		    Name="$(echo -e "increments/$Name").gz"	# Undo any \\ and \n escapes
		    [ ! -f "$Name" ] && Name="${Name%.gz}"
		    printf "%s\0" "$Name"
		done <"$Tmpdir/rmlist" | xargs -0 "${Action[@]}" --
		cp -fv --backup=numbered "$StatFile" "$StatFile"
		if [ $NULsep = 0 ]; then
		    cp -v "$Tmpdir/newstats" "${StatFile%.gz}" 2>&1 | sed "s/^/$Mark/" >&2
		else
		    tr '\n' '\0' <"$Tmpdir/newstats" >"${StatFile%.gz}"
		fi
		chmod 600 "${StatFile%.gz}"
		[[ "$StatFile" =~ \.gz$ ]] && \
		    gzip -f -9 -v "${StatFile%.gz}" 2>&1 | sed "s/^/$Mark/" >&2
		if [ -z "$Debug" ]; then
		    rm -r "$Tmpdir"
		    trap "" 0
		fi
	    elif [[ "$REPLY" =~ ^N ]]; then
		trap "" 0
		echo "${Mark}$Tmpdir not removed" >&2
		return 1
	    fi
	fi
    done
} # end function procfile()

renice 10 $$ >/dev/null
if [ $Nparallel = 1 ]; then
    procfile "${StatList[@]}"
else
    # Note: parallel processing management via fifo adapted from
    #       http://mywiki.wooledge.org/ProcessManagement
    # Uses file descriptor 9 for the fifo.
    Ptemp=$(mktemp -d ) || exit
    mkfifo -m 600 $Ptemp/xpipe || exit
    exec 9<>$Ptemp/xpipe
    rm -r $Ptemp
    [ $Nparallel -gt ${#StatList[*]} ] && Nparallel=${#StatList[*]}
    Njobs=0
    for ((Pindex=0; Pindex < Nparallel; ++Pindex)); do
	Marks[Pindex]=$((Pindex+1))
	( procfile -m ${Marks[Pindex]} ${StatList[Pindex]}; echo $Pindex $? >&9 )&
	JobIDs[Pindex]=$!
	((++Njobs))
    done
    BadRc=0
    while read Jobnum Rc Rest; do
#	echo "[${Marks[Jobnum]}] JobIDs[$Jobnum]=${JobIDs[Jobnum]} Rc=$Rc Rest=$Rest" >&2
	if [ $Rc != 0 ]; then
	    echo "[${Marks[Jobnum]}] Errors from procfile" >&2
	    BadRc=$Rc
	fi
	wait ${JobIDs[Jobnum]}	# Don't let the zombies accumulate
	((--Njobs))
	if [ $BadRc = 0 -a $Pindex -lt ${#StatList[*]} ]; then
	    Marks[Jobnum]=$((Pindex+1))
	    ( procfile -m ${Marks[Jobnum]} ${StatList[Pindex]}; echo $Jobnum $? >&9 )&
	    JobIDs[Jobnum]=$!
	    ((++Njobs))
	    ((++Pindex))
	else
	    [ $Njobs = 0 ] && break
	fi
    done <&9
    exit $BadRc
fi

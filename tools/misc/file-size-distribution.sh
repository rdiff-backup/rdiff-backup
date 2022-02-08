#!/bin/sh
# output the distribution of file sizes in a given directory
# (or the current one by default)

find ${1:-.} -type f -print0 | xargs -0 ls -l | \
	awk '
		{ size[int(log($5)/log(2))]++ }
		END {
			for (i in size) printf("%10d %5d\n", 2^i, size[i])
		}
	' | sort -n

#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool.

# OK, this is how we test feeding hsync it's own filth.  Starting
# with an empty signature, we generate the difference from one
# file to another.

source testfns.sh $0

files=`echo in-??`

for old in $files
do
    run_test hsencode $old lt.tmp /dev/null
    run_test hsdecode /dev/null sig.tmp old-out.tmp lt.tmp
    run_test cmp $old old-out.tmp
    for new in $files
    do 
	if [ $old != $new ] 
	then
	    run_test hsencode $new lt.tmp sig.tmp
	    run_test hsdecode $old /dev/null new-out.tmp lt.tmp
	    run_test cmp $new new-out.tmp
	fi
    done
done

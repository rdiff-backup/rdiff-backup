#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool.

# OK, this is how we test feeding hsync it's own filth.  Starting
# with an empty signature, we generate the difference from one
# file to another.

source ${srcdir:-.}/testfns.sh $0

files=`echo $testdir/in-??`
lt=$tmpdir/lt.tmp
sig=$tmpdir/sig.tmp
oldout=$tmpdir/old.tmp
newout=$tmpdir/new.tmp

for old in $files
do
    run_test hsencode $old $lt /dev/null
    run_test hsdecode /dev/null $sig $oldout $lt
    run_test cmp $old $oldout
    for new in $files
    do 
	if [ $old != $new ] 
	then
	    countdown
	    run_test hsencode $new $lt $sig
	    run_test hsdecode $old /dev/null $newout $lt
	    run_test cmp $new $newout
	fi
    done
done

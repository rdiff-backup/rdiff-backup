#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool.
# $Id$

# OK, this is how we test feeding hsync it's own filth.  Starting
# with an empty signature, we generate the difference from one
# file to another.

files=`echo $testdir/in-??`
lt=$tmpdir/lt.tmp
sig=$tmpdir/sig.tmp
oldout=$tmpdir/old.tmp
newout=$tmpdir/new.tmp

for old in $files
do
    run_test hsnad /dev/null <$old >$lt
    run_test hsdecode /dev/null $sig $oldout $lt
    run_test cmp $old $oldout
    for new in $files
    do 
	if [ $old != $new ] 
	then
	    countdown
	    run_test hsnad $sig <$new >$lt
	    run_test hsdecode $old /dev/null $newout $lt
	    run_test cmp $new $newout
	fi
    done
done

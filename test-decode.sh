#! /bin/sh -pe

# $Id$
# Copyright (C) 2000 by Martin Pool

# Regression test encoding and decoding by playing a suite of prerecorded
# differences

# We expect the automake-generated Makefile to pass in $srcdir, but if we're
# run from the commandline we may not have it.

newsig=$tmpdir/newsig.tmp
out=$tmpdir/out.tmp

for diff in $testdir/??-diff
do
    id=`basename $diff -diff`
    old=$testdir/$id-old
    
    run_test hsdecode $old $newsig $out $diff
    run_test cmp $out $testdir/$id-new
    run_test cmp $newsig $testdir/$id-sig
done
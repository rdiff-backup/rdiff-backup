#! /bin/sh -pe

# Regression test encoding and decoding by playing a suite of prerecorded
# differences

# We expect the automake-generated Makefile to pass in $srcdir, but if we're
# run from the commandline we may not have it.

source ${srcdir:-.}/testfns.sh $0

out=$tmpdir/out.tmp

for diff in $testdir/??-diff
do
    id=`basename $diff -diff`
    new=$testdir/$id-new
    sig=$testdir/$id-sig
    expect=$testdir/$id-out
    
    run_test hsencode $new $out $sig 32
    run_test cmp $out $expect
done

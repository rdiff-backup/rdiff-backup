#! /bin/sh -pe

# Regression test encoding and decoding by playing a suite of prerecorded
# differences

# We expect the automake-generated Makefile to pass in $srcdir, but if we're
# run from the commandline we may not have it.

source testfns.sh $0 $@

newsig=newsig.tmp
out=out.tmp

for diff in ??-diff
do
    id=`echo $diff|sed -e 's/-diff$//'`
    old=$id-old
    
    run_test hsdecode $old $newsig $out $diff
    run_test cmp $out $id-new
    run_test cmp $newsig $id-sig
done
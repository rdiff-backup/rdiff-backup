#! /bin/sh -pe

# Regression test encoding and decoding by playing a suite of prerecorded
# differences

# We expect the automake-generated Makefile to pass in $srcdir, but if we're
# run from the commandline we may not have it.

source testfns.sh $0

out=out.tmp

for diff in ??-diff
do
    id=`echo $diff|sed -e 's/-diff$//'`
    new=$id-new
    sig=$id-sig
    expect=$id-out
    
    run_test hsencode $new $out $sig 32
    run_test cmp $out $expect
done

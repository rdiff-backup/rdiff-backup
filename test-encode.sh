#! /bin/sh -pex

# Regression test encoding and decoding by playing a suite of prerecorded
# differences

# We expect the automake-generated Makefile to pass in $srcdir, but if we're
# run from the commandline we may not have it.

if [ "$srcdir" = "" ]
then
    srcdir=`dirname $0`
fi

PATH=`cd $srcdir; pwd`:$PATH
cd $srcdir/test-encode

out=out.tmp

for diff in ??-diff
do
    id=`echo $diff|sed -e 's/-diff$//'`
    echo -n $id ' '
    new=$id-new
    sig=$id-sig
    expect=$id-out
    
    hsencode $new $out $sig
    cmp $out $expect
done

echo
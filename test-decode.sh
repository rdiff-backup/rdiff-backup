#! /bin/sh -pe

# Regression test encoding and decoding by playing a suite of prerecorded
# differences

# We expect the automake-generated Makefile to pass in $srcdir, but if we're
# run from the commandline we may not have it.

echo -n `basename $0`': '

if [ "$srcdir" = "" ]
then
    srcdir=`dirname $0`
fi

PATH=`cd $srcdir; pwd`:$PATH
cd $srcdir/test-decode

newsig=newsig.tmp
out=out.tmp

for diff in ??-diff
do
    id=`echo $diff|sed -e 's/-diff$//'`
    echo -n $id ' '
    old=$id-old
    
    hsdecode $old $newsig $out $diff
    cmp $out $id-new
    cmp $newsig $id-sig
done

echo
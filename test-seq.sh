#! /bin/sh -pex

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool.

# OK, this is how we test feeding hsync it's own filth.  Starting
# with an empty signature, we generate the difference from one
# file to another.

if [ "$srcdir" = "" ]
then
    srcdir=`dirname $0`
fi
srcdir=`cd $srcdir; pwd`

PATH=$srcdir:$PATH
testdir=$srcdir/test-seq
[ -d $testdir ] || mkdir $testdir
cd $testdir

files=`echo in-??`

echo -n `basename $0` ' '

for old in $files
do
    echo -n '-'
    hsencode $old lt.tmp /dev/null
    hsdecode /dev/null sig.tmp old-out.tmp lt.tmp
    cmp $old old-out.tmp
    for new in $files
    do 
	if [ $old != $new ] 
	then
	    echo -n '.'
	    hsencode $new lt.tmp sig.tmp
	    hsdecode $old /dev/null new-out.tmp lt.tmp
	    cmp $new new-out.tmp
	fi
    done
done

echo 



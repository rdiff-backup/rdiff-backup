#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool

# This one makes sure that the signature calculated for a file is
# independant of the old file we're comparing it to.

# `What I tell you three times is true'

if [ "$srcdir" = "" ]
then
    srcdir=`dirname $0`
fi
srcdir=`cd $srcdir; pwd`

PATH=$srcdir:$PATH

testdir=$srcdir/test-thrice
[ -d $testdir ] || mkdir $testdir
cd $testdir

echo -n `basename $0` ' '

data=../INSTALL

rm -f *.tmp

hsencode $data lt.tmp /dev/null
hsdecode $data sig01.tmp new01.tmp lt.tmp
cmp $data new01.tmp

hsencode $data lt.tmp sig01.tmp 
hsdecode $data sig02.tmp new02.tmp lt.tmp
cmp sig01.tmp sig02.tmp
cmp $data new02.tmp

hsencode $data lt.tmp sig02.tmp
hsdecode $data sig03.tmp new03.tmp lt.tmp
cmp sig02.tmp sig03.tmp
cmp $data new03.tmp

#! /bin/sh -pe

# Regression test binary command encoding by spitting lots of 
# stuff from ascii to binary and back.

# We expect the automake-generated Makefile to pass in $srcdir, but if we're
# run from the commandline we may not have it.

if [ "$srcdir" = "" ]
then
    srcdir=`dirname $0`
fi

PATH=`cd $srcdir; pwd`:$PATH
cd $srcdir/test-cmds

out=out.tmp
cmds=cmds.txt
tmp=bin.tmp

hsemit < $cmds > $tmp
hsinhale > $out < $tmp
diff -b -q $out $cmds

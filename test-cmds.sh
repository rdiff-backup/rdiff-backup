#! /bin/sh -pe

# Regression test binary command encoding by spitting lots of 
# stuff from ascii to binary and back.

# We expect the automake-generated Makefile to pass in $srcdir, but if we're
# run from the commandline we may not have it.

source ${srcdir:=.}/testfns.sh $0 $@

out=$tmpdir/out.tmp
cmds=$testdir/cmds.txt
tmp=$tmpdir/bin.tmp

run_test hsemit < $cmds > $tmp
run_test hsinhale > $out < $tmp
run_test diff -b -q $out $cmds

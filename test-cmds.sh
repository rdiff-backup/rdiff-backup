#! /bin/sh -pe

# $Id$
# Copyright (C) 2000 by Martin Pool

# Regression test binary command encoding by spitting lots of 
# stuff from ascii to binary and back.

# We expect the automake-generated Makefile to pass in $srcdir, but if we're
# run from the commandline we may not have it.

out=$tmpdir/out.tmp
cmds=$testdir/cmds
tmp=$tmpdir/bin.tmp

run_test hsemit < $cmds > $tmp
run_test hsinhale > $out < $tmp
run_test diff -b -q $out $cmds

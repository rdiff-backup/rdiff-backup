#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool

# This one makes sure that the signature calculated for a file is
# independant of the old file we're comparing it to.

# `What I tell you three times is true'

source ${srcdir:-.}/testfns.sh $0 $@

data=$testdir/01-data

rm -f *.tmp

run_test hsencode $data $tmpdir/lt.tmp /dev/null
run_test hsdecode $data $tmpdir/sig01.tmp $tmpdir/new01.tmp $tmpdir/lt.tmp
run_test cmp $data $tmpdir/new01.tmp

run_test hsencode $data $tmpdir/lt.tmp $tmpdir/sig01.tmp 
run_test hsdecode $data $tmpdir/sig02.tmp $tmpdir/new02.tmp $tmpdir/lt.tmp
run_test cmp $tmpdir/sig01.tmp $tmpdir/sig02.tmp
run_test cmp $data $tmpdir/new02.tmp

run_test hsencode $data $tmpdir/lt.tmp $tmpdir/sig02.tmp
run_test hsdecode $data $tmpdir/sig03.tmp $tmpdir/new03.tmp $tmpdir/lt.tmp
run_test cmp $tmpdir/sig02.tmp $tmpdir/sig03.tmp
run_test cmp $data $tmpdir/new03.tmp

#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool

# This one makes sure that the signature calculated for a file is
# independant of the old file we're comparing it to.

# `What I tell you three times is true'

source ${srcdir:-.}/testfns.sh $0 $@

files=`find ${srcdir:-.} -type f|head -100`

for data in $files
do
run_test hsnad /dev/null <$data >$tmpdir/lt.tmp
run_test hsdecode $data $tmpdir/sig01.tmp $tmpdir/new01.tmp $tmpdir/lt.tmp
run_test cmp $data $tmpdir/new01.tmp

run_test hsnad $tmpdir/sig01.tmp <$data >$tmpdir/lt.tmp 
run_test hsdecode $data $tmpdir/sig02.tmp $tmpdir/new02.tmp $tmpdir/lt.tmp
run_test cmp $tmpdir/sig01.tmp $tmpdir/sig02.tmp
run_test cmp $data $tmpdir/new02.tmp

run_test hsnad  $tmpdir/sig02.tmp <$data >$tmpdir/lt.tmp
run_test hsdecode $data $tmpdir/sig03.tmp $tmpdir/new03.tmp $tmpdir/lt.tmp
run_test cmp $tmpdir/sig02.tmp $tmpdir/sig03.tmp
run_test cmp $data $tmpdir/new03.tmp
done
#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool

# This one makes sure that the signature calculated for a file is
# independant of the old file we're comparing it to.

# `What I tell you three times is true'

source ${srcdir:-.}/testfns.sh $0 $@

data=../INSTALL

rm -f *.tmp

run_test hsencode $data lt.tmp /dev/null
run_test hsdecode $data sig01.tmp new01.tmp lt.tmp
run_test cmp $data new01.tmp

run_test hsencode $data lt.tmp sig01.tmp 
run_test hsdecode $data sig02.tmp new02.tmp lt.tmp
run_test cmp sig01.tmp sig02.tmp
run_test cmp $data new02.tmp

run_test hsencode $data lt.tmp sig02.tmp
run_test hsdecode $data sig03.tmp new03.tmp lt.tmp
run_test cmp sig02.tmp sig03.tmp
run_test cmp $data new03.tmp

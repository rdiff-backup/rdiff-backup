#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool
# $Id$

# This one makes sure that the signature calculated for a file is
# independant of the old file we're comparing it to.

# `What I tell you three times is true'

# FIXME: Some of the temporary files generated are too large.

# FIXME: The source and build files will tend to vary a lot between
# runs and not necessarily cover all equivalencies.  Therefore instead
# use a program to generate appropriate files -- will subsets of
# COPYING be enough?

orig=$srcdir/COPYING
data=$tmpdir/data

for instr1 in $delta_instr
do
    run_test hsmapread $debug $instr1 <$orig >$data

    run_test hsnad $debug /dev/null <$data >$tmpdir/lt.tmp
    run_test hsdecode $debug $data $tmpdir/sig01.tmp $tmpdir/new01.tmp $tmpdir/lt.tmp
    run_test cmp $data $tmpdir/new01.tmp

    run_test hsnad $debug $tmpdir/sig01.tmp <$data >$tmpdir/lt.tmp 
    run_test hsdecode $debug $data $tmpdir/sig02.tmp $tmpdir/new02.tmp $tmpdir/lt.tmp
    run_test cmp $tmpdir/sig01.tmp $tmpdir/sig02.tmp
    run_test cmp $data $tmpdir/new02.tmp

    run_test hsnad  $debug $tmpdir/sig02.tmp <$data >$tmpdir/lt.tmp
    run_test hsdecode $debug $data $tmpdir/sig03.tmp $tmpdir/new03.tmp $tmpdir/lt.tmp
    run_test cmp $tmpdir/sig02.tmp $tmpdir/sig03.tmp
    run_test cmp $data $tmpdir/new03.tmp
    countdown
done

run_test rm -f $tmpdir/sig0[123].tmp $tmpdir/new0[123].tmp $data

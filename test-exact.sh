#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool
# $Id$

# This driver generates a signature, and then checks it against the
# same file.  This ought to generate an exact match, including for the
# short block at the end.

old=$srcdir/COPYING
lt=$tmpdir/lt.tmp
oldsig=$tmpdir/oldsig.tmp
newsig=$tmpdir/newsig.tmp
newout=$tmpdir/out.tmp
chksig=$tmpdir/chksig.tmp
chkout=$tmpdir/chkout.tmp

run_test hsnad /dev/null <$old >$lt
run_test hsdecode /dev/null $oldsig /dev/null $lt
# run_test hsdumpsums <$oldsig
run_test hsnad $debug $stats $oldsig <$old >$lt

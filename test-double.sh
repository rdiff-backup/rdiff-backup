#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool
# $Id$

# This driver tests matching one file against a shorter prefix.  This
# should test handling of short blocks and so on.

old=$srcdir/COPYING
new=$tmpdir/new.tmp
lt=$tmpdir/lt.tmp
oldsig=$tmpdir/oldsig.tmp
newsig=$tmpdir/newsig.tmp
newout=$tmpdir/out.tmp
chksig=$tmpdir/chksig.tmp
chkout=$tmpdir/chkout.tmp

run_test cat $old $old >$new

run_test hsnad /dev/null <$old >$lt
run_test hsdecode /dev/null $oldsig /dev/null $lt
# run_test hsdumpsums <$oldsig
run_test hsnad $debug $stats $oldsig <$new >$lt
run_test hsdecode $old $newsig $newout $lt
run_test cmp $new $newout
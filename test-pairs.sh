#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool
# $Id$

# This test case tries to transform one file into another using
# various hsmapread instructions.  It then checks transforming between
# the new and old files, and back again.

old=$srcdir/COPYING
lt=$tmpdir/lt.tmp
oldsig=$tmpdir/oldsig.tmp
newsig=$tmpdir/newsig.tmp
newout=$tmpdir/out.tmp
chksig=$tmpdir/chksig.tmp
chkout=$tmpdir/chkout.tmp

run_test hsnad $debug /dev/null <$old >$lt
run_test hsdecode $debug /dev/null $oldsig /dev/null $lt
    
for instr in $delta_instr
do
    new="$tmpdir/new$instr.tmp"

    run_test hsmapread $debug $instr <$old >$new
    
    run_test hsnad $debug $oldsig <$new >$lt
    run_test hsdecode $debug $old $newsig $newout $lt
    run_test cmp $new $newout

    run_test hsnad $debug $newsig <$old >$lt
    run_test hsdecode $debug $new $chksig $chkout $lt
    run_test cmp $chkout $old
    countdown
done

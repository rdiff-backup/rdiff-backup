#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool
# $Id$

# This test case tries to transform one file into another using
# various hsmapread instructions.  It then checks transforming between
# the new and old files, and back again.

# TODO: Add more pair instructions here
pairinstr="
0,1
0,10
0,1000
0,10000
0,100000
1,10
1,10000
0,2000:2000,2000:4000,100000
"

old=$srcdir/COPYING
lt=$tmpdir/lt.tmp
oldsig=$tmpdir/oldsig.tmp
newsig=$tmpdir/newsig.tmp
newout=$tmpdir/out.tmp
chksig=$tmpdir/chksig.tmp
chkout=$tmpdir/chkout.tmp

run_test hsnad /dev/null <$old >$lt
run_test hsdecode /dev/null $oldsig /dev/null $lt
    
for instr in $pairinstr
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

#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool
# $Id$

# Generate and test differences based on compinations of source files.

diff=$tmpdir/diff.tmp
newsig=$tmpdir/newsig.tmp
old=$tmpdir/old.tmp
new=$tmpdir/new.tmp
out=$tmpdir/out.tmp
oldsig=$tmpdir/oldsig.tmp
fromsig=$tmpdir/fromsig.tmp
fromlt=$tmpdir/fromlt.tmp
ltfile=$tmpdir/lt.tmp

basis=$srcdir/COPYING

for instr1 in $delta_instr
do
    run_test hsmapread $debug $instr1 <$basis >$old

    run_test hsnad $debug /dev/null <$old >$ltfile
    run_test hsdecode $debug /dev/null $oldsig /dev/null $ltfile 

    for instr2 in $delta_instr
    do
	countdown
	run_test hsmapread $debug $instr1 <$basis >$new

	run_test hsnad $debug $oldsig <$new >$diff 
        run_test hsdecode $debug $old $newsig $out $diff 
   
        run_test cmp $out $new
   done
done
    
    

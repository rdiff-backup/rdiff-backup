#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool

# OK, no

source ${srcdir:-.}/testfns.sh $0 $@

diff=$tmpdir/diff.tmp
files=`echo $srcdir/*.c|head -20`
out=$tmpdir/out.tmp
sig=$tmpdir/sig.tmp
newsig=$tmpdir/newsig.tmp
old=/dev/null

fromsig=$tmpdir/fromsig.tmp
fromlt=$tmpdir/fromlt.tmp
ltfile=$tmpdir/lt.tmp

for from in $files
do
    run_test hsnad /dev/null <$from >$ltfile
    run_test hsdecode /dev/null $sig $out $ltfile

    run_test cmp $out $from

    for new in $files
    do
        run_test hsnad $sig <$new >$diff
        run_test hsdecode $old $newsig $out $diff 
    
        run_test cmp $out $new
    done
done
    
    

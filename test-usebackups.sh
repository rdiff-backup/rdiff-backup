#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool

# Use any emacs backup files we can find lying around as test 
# cases.

source ${srcdir:-.}/testfns.sh $0 $@

diff=$tmpdir/diff.tmp
out=$tmpdir/out.tmp
sig=$tmpdir/sig.tmp
newsig=$tmpdir/newsig.tmp
old=/dev/null

fromsig=$tmpdir/fromsig.tmp
fromlt=$tmpdir/fromlt.tmp
ltfile=$tmpdir/lt.tmp

# for every backup file
for from in $srcdir/*~
do
    # continue if this is not a readable file
    [ -f $from -a -r $from ] || continue

    # find the corresponding current file
    new=`echo $from | sed -e 's/\.~.*$//' -e 's/~$//' `

    # continue if this is not readable; most likely
    # this is because the glob didn't expand to anything
    [ -f $new -a -r $new ] || continue

    countdown
    
    run_test hsnad $test_opts /dev/null <$from >$ltfile
    run_test hsdecode $test_opts /dev/null $sig $out $ltfile

    run_test cmp $out $from

    run_test hsnad $test_opts $sig <$new >$diff
    run_test hsdecode $test_opts $old $newsig $out $diff 
    
    run_test cmp $out $new
done
    
    

#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool

source ${srcdir:-.}/testfns.sh $0 $@

diff=$tmpdir/diff.tmp
files=`echo $srcdir/*.c|head -20`
newsig=$tmpdir/newsig.tmp
out=$tmpdir/out.tmp
oldsig=empty-sig
old=/dev/null

fromsig=$tmpdir/fromsig.tmp
fromlt=$tmpdir/fromlt.tmp
ltfile=$tmpdir/lt.tmp

for from in $files
do
    run_test hsencode $from $ltfile /dev/null
#      hsdecode $from 

#      for new in $files
#      do
#          echo -n '.'
#          hsencode $new $diff $oldsig
#          hsdecode $old $newsig $out $diff 
    
#          cmp $out $new
#      done
    
done
    
    

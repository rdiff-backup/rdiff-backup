#! /bin/sh -pe

# Regression test suite for libhsync.

# Copyright (C) 2000 by Martin Pool

# OK, this is how we test feeding hsync it's own filth.  Starting
# with an empty signature, we generate the difference from one
# file to another.

source testfns.sh $0 $@

diff=diff.tmp
files=`echo $srcdir/*.c|head -20`
newsig=newsig.tmp
out=out.tmp
oldsig=empty-sig
old=/dev/null

fromsig=fromsig.tmp
fromlt=fromlt.tmp

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
    
    

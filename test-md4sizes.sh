#! /bin/sh -pex

# Copyright (C) 2000 by Martin Pool

# Test running the mdfour algorithm with different buffer sizes.  We
# should get the same result in every case.

source ${srcdir:-.}/testfns.sh $0 $@

files=`echo $srcdir/INSTALL`

sizes="1 2 3 4 7 8 9 10 33 63 64 65 100 200 2000 10000"

rm -f old.tmp

for from in $files
do
    for size in $sizes
    do
	run_test hsmdfour -b $size <$from >new.tmp
	[ -f old.tmp ] && run_test cmp old.tmp new.tmp
	mv new.tmp old.tmp
    done
done
    
    

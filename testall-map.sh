#! /bin/sh

# Shortcut to test all mapptr functions

for t in mapread mapover mappipe mapeof
do 
    ./test-$t.sh
done

#! /bin/bash -pe

# Copyright (C) 2000 by Martin Pool
# $Id$

# Test that the test harness kind of works

# We expect this one to work OK
run_test true love

# And this one not to work
run_test false pretenses

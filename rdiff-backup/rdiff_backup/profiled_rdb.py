#!/usr/bin/env python

"""Run rdiff-backup with profiling on

Same as rdiff-backup but runs profiler, and prints profiling
statistics afterwards.

"""

__no_execute__ = 1
execfile("main.py")
import profile, pstats
profile.run("Globals.Main.Main(%s)" % repr(sys.argv[1:]), "profile-output")
p = pstats.Stats("profile-output")
p.sort_stats('time')
p.print_stats(20)
p.sort_stats('cumulative')
p.print_stats(20)



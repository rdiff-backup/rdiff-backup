#!/usr/bin/env python

"""Run rdiff-backup with profiling on

Same as rdiff-backup but runs profiler, and prints profiling
statistics afterwards.

"""

__no_execute__ = 1
import sys, rdiff_backup.Main, profile, pstats
profile.run("rdiff_backup.Main.Main(%s)" % repr(sys.argv[1:]),
			"profile-output")
p = pstats.Stats("profile-output")
p.sort_stats('time')
p.print_stats(40)
#p.print_callers(20)



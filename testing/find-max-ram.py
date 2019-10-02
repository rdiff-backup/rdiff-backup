#!/usr/bin/env python3
"""find-max-ram - Returns the maximum amount of memory used by a program.

Every half second, run ps with the appropriate commands, getting the
size of the program.  Return max value.

"""

import os
import sys
import time
from functools import reduce


def get_val(cmdstr):
    """Runs ps and gets sum rss for processes making cmdstr

    Returns None if process not found.

    """
    cmd = ("ps -Ao cmd -o rss | grep '%s' | grep -v grep" % cmdstr)
    # print "Running ", cmd
    fp = os.popen(cmd)
    lines = fp.readlines()
    fp.close()

    if not lines:
        return None
    else:
        return reduce(lambda x, y: x + y, list(map(read_ps_line, lines)))


def read_ps_line(psline):
    """Given a specially formatted line by ps, return rss value"""
    pslist = psline.split()
    assert len(pslist) >= 2  # first few are name, last one is rss
    return int(pslist[-1])


def main(cmdstr):
    while get_val(cmdstr) is None:
        time.sleep(0.5)

    current_max = 0
    while 1:
        rss = get_val(cmdstr)
        print(rss)
        if rss is None:
            break
        current_max = max(current_max, rss)
        time.sleep(0.5)

    print(current_max)


if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("""Usage: find-max-ram [command string]

                It will then run ps twice a second and keep totalling how much RSS
                (resident set size) the process(es) whose ps command name contain the
                given string use up.  When there are no more processes found, it will
                print the number and exit.
                """)
        sys.exit(1)
    else:
        main(sys.argv[1])

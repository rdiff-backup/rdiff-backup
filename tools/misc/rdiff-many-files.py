#!/usr/bin/env python3
"""Run rdiff to transform everything in one dir to another"""

import subprocess
import sys

def os_system(*call):
    subprocess.run(call, check=True)

dir1, dir2 = sys.argv[1:3]
for i in range(1000):
    os_system("rdiff", "signature", f"{dir1}/{i}", "sig")
    os_system("rdiff", "delta", "sig", f"{dir2}/{i}", "diff")
    os_system("rdiff", "patch", f"{dir1}/{i}", "diff", f"{dir1}/{i}.out")

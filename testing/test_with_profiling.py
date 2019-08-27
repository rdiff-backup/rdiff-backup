import profile
import pstats
import os

# if you need to profile a certain test, replace the "metadatatest" placeholder
# with the test you want to profile and all functions will get imported into
# the current namespace.
# I didn't find a way to do it dynamically...
from metadatatest import *  # noqa: F403, F401 star import and unused

# Create a profile output filename (don't forget to adapt the name)
abs_work_dir = os.getenvb(
    b'TOX_ENV_DIR',
    os.getenvb(b'VIRTUAL_ENV', os.path.join(os.getcwdb(), b'build')))
profile_output = os.path.join(abs_work_dir, b"profile-metadatatest.out")

# Run and output the test profile
profile.run("unittest.main()", profile_output)
p = pstats.Stats(profile_output)
p.sort_stats('time')
p.print_stats(40)

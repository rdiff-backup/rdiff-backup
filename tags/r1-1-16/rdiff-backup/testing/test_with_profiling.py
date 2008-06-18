import profile, pstats
from metadatatest import *

profile.run("unittest.main()", "profile-output")
p = pstats.Stats("profile-output")
p.sort_stats('time')
p.print_stats(40)

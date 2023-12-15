# write the hook file which will make sure that coverage is loaded
# also for sub-processes, like for "client/server" rdiff-backup

import os
import site
import sys

for site_path in sys.path:
    coverage_pth = os.path.join(site_path, "coverage.pth")
    if os.path.isfile(coverage_pth):
        print("The file {} exists already".format(coverage_pth))
        sys.exit(0)

if site.ENABLE_USER_SITE:
    site_packages = [site.getusersitepackages()]
else:  # we're probably in a virtualenv
    site_packages = reversed(site.getsitepackages())

for site_path in site_packages:
    coverage_pth = os.path.join(site_path, "coverage.pth")
    try:
        os.makedirs(site_path, exist_ok=True)
        with open(coverage_pth, "w") as fd:
            fd.write("import coverage; coverage.process_startup()\n")
            print("The file {} has been written".format(coverage_pth))
            sys.exit(0)
    except OSError as exc:
        print("Couldn't write the file {} due to {}".format(coverage_pth, exc))

print("The coverage.pth file could be written nowhere")
sys.exit(1)

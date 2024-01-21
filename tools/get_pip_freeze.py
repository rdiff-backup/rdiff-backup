#!/usr/bin/env python3
# because pip freeze doesn't offer a way to give an output file, and tox
# doesn't have a shell for redirection, we need to write our own pip freeze
# https://stackoverflow.com/questions/24321933/programmatically-generate-requirements-txt-file
# Call with `./tools/get_pip_freeze.py <outputfile>`

import sys
import importlib.metadata as ilmd

installed = {pkg for pkgs in ilmd.packages_distributions().values() for pkg in pkgs}
req_str = "\n".join(f"{pkg}=={ilmd.version(pkg)}" for pkg in sorted(installed))

with open(sys.argv[1], "w") as f:
    f.write(req_str)

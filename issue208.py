#!/usr/bin/env python3

# This script creates a set of files and directories for testing
# rdiff-backup.
# The first run creates the files and directories.
# Subsequent runs update the contents of all files.
# The contents are taken from a "template" file, that is updated at every run.

import sys
import os.path

# Number of directories
dirCount = 10
# Number of files inside each directory
fileCount = 60;

if (len(sys.argv) < 2) or (sys.argv[1] in ("-h", "--help")):
    sys.stderr.write("Usage: %s dest_path\n" % sys.argv[0])
    sys.exit(1)

# Prepare or update the template
fileContents = ""
destPath = sys.argv[1]
if not os.path.isdir(destPath):
    os.mkdir(destPath)
templateFileName = os.path.join(destPath, "template.txt")
if os.path.exists(templateFileName):
    fileContents = int(open(templateFileName, "r").read())
else:
    fileContents = 0
fileContents = str(fileContents + 1)
with open(templateFileName, "w") as f:
    f.write(fileContents)
    
for dirIndex in range(0, dirCount):
    dirPath = os.path.join(destPath, "dir%04d" % (dirIndex + 1))
    if not os.path.isdir(dirPath):
        os.mkdir(dirPath)
    for fileIndex in range (0, fileCount):
        filePath = os.path.join(dirPath, "file%04d" % (fileIndex + 1))
        with open(filePath, "w") as f:
            f.write(fileContents)

"""commontest - Some functions and constants common to all test cases"""
import os

SourceDir = "../src"
AbsCurdir = os.getcwd() # Absolute path name of current directory
AbsTFdir = AbsCurdir+"/testfiles"
MiscDir = "../misc"

def rbexec(src_file):
	"""Changes to the source directory, execfile src_file, return"""
	os.chdir(SourceDir)
	execfile(src_file, globals())
	os.chdir(AbsCurdir)

def Make():
	"""Make sure the rdiff-backup script in the source dir is up-to-date"""
	os.chdir(SourceDir)
	os.system("python ./Make")
	os.chdir(AbsCurdir)

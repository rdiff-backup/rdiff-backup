# CMake generated Testfile for 
# Source directory: /home/sadam/librsync-mah
# Build directory: /home/sadam/librsync-mah
# 
# This file includes the relevant testing commands required for 
# testing this directory and lists subdirectories to be tested as well.
add_test(Help "help.test")
set_tests_properties(Help PROPERTIES  WORKING_DIRECTORY "/home/sadam/librsync-mah/tests")
add_test(Isprefix "isprefix.test")
set_tests_properties(Isprefix PROPERTIES  WORKING_DIRECTORY "/home/sadam/librsync-mah/tests")
add_test(Mutate "mutate.test")
set_tests_properties(Mutate PROPERTIES  WORKING_DIRECTORY "/home/sadam/librsync-mah/tests")
add_test(Signature "signature.test")
set_tests_properties(Signature PROPERTIES  WORKING_DIRECTORY "/home/sadam/librsync-mah/tests")
add_test(Sources "sources.test")
set_tests_properties(Sources PROPERTIES  WORKING_DIRECTORY "/home/sadam/librsync-mah/tests")
add_test(Triple "triple.test")
set_tests_properties(Triple PROPERTIES  WORKING_DIRECTORY "/home/sadam/librsync-mah/tests")
add_test(Delta "delta.test")
set_tests_properties(Delta PROPERTIES  WORKING_DIRECTORY "/home/sadam/librsync-mah/tests")
add_test(Changes "changes.test")
set_tests_properties(Changes PROPERTIES  WORKING_DIRECTORY "/home/sadam/librsync-mah/tests")
subdirs(tests)

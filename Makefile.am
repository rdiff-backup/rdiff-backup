## Process this file with automake to produce Makefile.in

# Copyright (C) 2000 by Martin Pool
# $Id$

lib_LTLIBRARIES = libhsync.la

libhsync_la_LDFLAGS = -version-info @libhsync_libversion@

libhsync_la_SOURCES = \
	dec.c \
	emit.c emit.h \
	litbuf.c \
	private.h \
	netio.c netio.h \
	includes.h \
	mdfour.c \
	filebuf.c membuf.c ptrbuf.c \
	checksum.c checksum.h \
	sum_p.h \
	copyq.c \
	inbuf.c \
	inhale.c \
	trace.c trace.h \
	hex.c stats.c \
	mapptr.c mapptr.h map_p.h \
	fileutil.c fileutil.h \
	gdproto.c \
	util.c util.h \
	mksum.c mksum.h \
	sumset.c sumset.h \
	rollsum.c rollsum.h \
	nad.c nad_p.h nadsrch.c nadout.c \
	search.c search.h

# TODO: If we ever care enough, build a second library containing only
# the code necessary to be a client, and not stuff for encoding.  At
# the moment it doesn't seem worth the additional compilation time to
# do both, and I don't know if anyone will care if they're just shared
# libraries anyhow.

# NB: tests should exit with code 77 if they can't be run but haven't failed.

# Generally these tests should be ordered so that more basic tests
# are run first.

# TODO: driver.sh requires bash.  Therefore we should either test for
# it and use it rather than $SHELL, or we should rewrite it to work in
# plain Bourne shell.

TESTS_ENVIRONMENT = $(SHELL) $(srcdir)/driver.sh
test_scripts = \
	test-maptcp.sh \
	test-tricky.sh \
	test-chain.sh \
	test-md4sizes.sh \
	test-cat.sh \
	test-mapread.sh \
	test-cmds.sh \
	test-thrice.sh \
	test-mappipe.sh \
	test-mapeof.sh \
	test-mapover.sh \
	test-nadsum.sh \
	test-pairs.sh \
	test-exact.sh \
	test-double.sh

# These are extra documents to be included in the source tarball.
extra_docs = README.CVS

# These ones are not tests, but are useful in watching the code run
# through.
try_scripts = 

# Thus spake the master programmer:
#
# ``When the program is being tested, it is too late to make design
# changes.''

TESTS = $(test_scripts)

noinst_SCRIPTS = \
	$(test_scripts) \
	driver.sh \
	test-meta.sh \
	$(try_scripts)

test_data= \
	test-cmds.in \
in-tricky/in-01					\
in-tricky/in-02					\
in-tricky/in-03					\
in-tricky/in-04					\
in-tricky/in-05					\
in-tricky/in-06					\
in-tricky/in-07

# TODO: Delete the test-*.d directories when cleaning up.  Yeah!
CLEANFILES = tmp-test-*.d/* tmp-try-*.d/*

EXTRA_DIST = $(noinst_SCRIPTS) $(test_data) $(extra_docs)

include_HEADERS = hsync.h hsyncproto.h

# This is the default for any programs that don't specify a
# preference.
LDADD = libhsync.la

bin_PROGRAMS = hsdecode hsmdfour hsmksum hsmapread hsnad \
		libhsyncinfo
noinst_PROGRAMS = hsdumpsums
check_PROGRAMS = hsemit hsinhale hsfilebufcat genmaptest \
	socksvr sockcli sockrun trylog

.PHONY: check_programs
check_programs: $(check_PROGRAMS)

trylog_SOURCES = trylog.c 

sockrun_SOURCES = sockrun.c trace.c util.c fileutil.c
sockrun_LDADD = @net_libs@

socksvr_SOURCES = socksvr.c trace.c util.c
socksvr_LDADD = @net_libs@

sockcli_SOURCES = sockcli.c trace.c util.c fileutil.c
sockcli_LDADD = @net_libs@

genmaptest_LDADD =

hsfilebufcat_SOURCES = hsfilebufcat.c trace.c util.c filebuf.c netio.c fileutil.c
hsfilebufcat_LDADD =

libhsyncinfo_SOURCES = libhsyncinfo.c

hsnad_SOURCES = hsnad.c

hsmksum_SOURCES = hsmksum.c

hsmdfour_SOURCES = hsmdfour.c

hsdecode_SOURCES = hsdecode.c

hsemit_SOURCES = hsemit.c

hsinhale_SOURCES = hsinhale.c

hsmapread_SOURCES = hsmapread.c filebuf.c util.c trace.c fileutil.c \
	mapptr.c
hsmapread_LDADD =

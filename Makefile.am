## Process this file with automake to produce Makefile.in
## Copyright (C) 2000 by Martin Pool

## $Id$

lib_LTLIBRARIES = libhsync.la

# This is NOT the libhsync release number.  Rather, it is a
# CURRENT:REVISION:AGE tuple describing binary compatibility to
# libtool.
libhsync_la_LDFLAGS = -version-info @libhsync_libversion@

libhsync_la_SOURCES = dec.c enc.c \
	emit.c emit.h \
	litbuf.c \
	private.h \
	netio.c netio.h \
	includes.h \
	mdfour.c \
	search.c search.h \
	filebuf.c membuf.c ptrbuf.c \
	checksum.c checksum.h \
	copyq.c \
	inbuf.c \
	inhale.c \
	trace.c trace.h \
	hex.c stats.c \
	mapptr.c mapptr.h \
	fileutil.c \
	gdproto.c \
	util.c util.h \
	mksum.c mksum.h \
	sumset.c sumset.h \
	rollsum.c rollsum.h \
	nad.c 

# NB: tests should exit with code 77 if they can't be run but haven't failed.
TESTS_ENVIRONMENT = $(SHELL)
test_scripts := \
	test-tricky.sh \
	test-chain.sh \
	test-seqnad.sh \
	test-md4sizes.sh \
	test-cat.sh \
	test-mapread.sh \
	test-cmds.sh \
	test-thrice.sh \
	test-usebackups.sh \
	test-seq.sh \
	test-mappipe.sh \
	test-mapeof.sh \
	test-mapover.sh \
	test-nadsum.sh \
	test-thricenad.sh

noinst_SCRIPTS = \
	$(test_scripts) \
	testfns.sh

test_data=test-chain/empty-sig			\
test-decode/01-diff				\
test-decode/01-new				\
test-decode/01-old				\
test-decode/01-sig				\
test-decode/02-diff				\
test-decode/02-new				\
test-decode/02-old				\
test-decode/02-sig				\
test-decode/03-diff				\
test-decode/03-new				\
test-decode/03-old				\
test-decode/03-sig				\
test-decode/04-diff				\
test-decode/04-new				\
test-decode/04-old				\
test-decode/04-sig				\
test-decode/05-diff				\
test-decode/05-new				\
test-decode/05-old				\
test-decode/05-sig				\
test-decode/README				\
test-encode/01-diff				\
test-encode/01-new				\
test-encode/01-out				\
test-encode/01-sig				\
test-seq/in-01					\
test-seq/in-04					\
test-seq/in-07					\
test-seq/in-08					\
test-cmds/cmds					\
test-thrice/01-data				\
in-tricky/in-01					\
in-tricky/in-02					\
in-tricky/in-03					\
in-tricky/in-04					\
in-tricky/in-05					\
in-tricky/in-06					\
in-tricky/in-07


# TODO: Delete the test-*.d directories when cleaning up.  Yeah! 
CLEANFILES = test-*.d/*

EXTRA_DIST = $(noinst_SCRIPTS) $(test_data)

include_HEADERS = hsync.h hsyncproto.h

# This is the default for any programs that don't specify a
# preference.
LDADD = libhsync.la

bin_PROGRAMS = hsdecode hsencode hsmdfour hsmksum hsmapread hsnad \
		libhsyncinfo
check_PROGRAMS = hsemit hsinhale hsfilebufcat genmaptest \
	socksvr

socksvr_SOURCES = socksvr.c trace.c util.c
socksvr_LDADD =

libhsyncinfo_SOURCES = libhsyncinfo.c

hsnad_SOURCES = hsnad.c

hsmksum_SOURCES = hsmksum.c

hsmdfour_SOURCES = hsmdfour.c 

hsfilebufcat_SOURCES = hsfilebufcat.c

hsdecode_SOURCES = hsdecode.c

hsencode_SOURCES = hsencode.c

hsemit_SOURCES = hsemit.c

hsinhale_SOURCES = hsinhale.c

hsmapread_SOURCES = hsmapread.c 

# Thus spake the master programmer:
# 
# ``When the program is being tested, it is too late to make design
# changes.''

TESTS = $(test_scripts)
## Process this file with automake to produce Makefile.in
## Copyright (C) 2000 by Martin Pool

## $Id$

CFLAGS += -W -Wall -g @DEFS@

lib_LTLIBRARIES = libhsync.la libhsyncdecode.la

libhsync_la_SOURCES = dec.c enc.c \
	emit.h emit.c \
	litbuf.c \
	private.h netio.c includes.h \
	mdfour.c search.c \
	filebuf.c membuf.c ptrbuf.c \
	checksum.c copyq.c \
	inbuf.c \
	inhale.c trace.c \
	hex.c stats.c mapptr.c fileutil.c \
	gdproto.c readsums.c

# compress.c compress.h 

libhsyncdecode_la_SOURCES = dec.c \
	private.h netio.c includes.h \
	compress.c compress.h \
	filebuf.c membuf.c ptrbuf.c \
	inhale.c trace.c hex.c stats.c  \
	mdfour.c fileutil.c mapptr.c \
	readsums.c

noinst_SCRIPTS = test-decode.sh test-encode.sh \
	test-chain.sh test-cmds.sh \
	make-cmds.py test-thrice.sh test-seq.sh test-meta.sh \
	test-cat.sh \
	test-md4sizes.sh testfns.sh \
	test-mapread.sh gen-maptest.py \
	test-mapover.sh gen-mapover.py \
	test-mappipe.sh gen-inbuftest.py \
	test-mapeof.sh 

test_data=test-chain/empty-sig  \
test-decode/01-diff \
test-decode/01-new \
test-decode/01-old \
test-decode/01-sig \
test-decode/02-diff \
test-decode/02-new \
test-decode/02-old \
test-decode/02-sig \
test-decode/03-diff \
test-decode/03-new \
test-decode/03-old \
test-decode/03-sig \
test-decode/04-diff \
test-decode/04-new \
test-decode/04-old \
test-decode/04-sig \
test-decode/05-diff \
test-decode/05-new \
test-decode/05-old \
test-decode/05-sig \
test-decode/README \
test-encode/01-diff \
test-encode/01-new \
test-encode/01-out \
test-encode/01-sig \
test-seq/in-01 \
test-seq/in-04 \
test-seq/in-07 \
test-seq/in-08 \
test-cmds/cmds \
test-thrice/01-data

# TODO: Delete the test-*.d directories when cleaning up.  Yeah! 
CLEANFILES = test-*.d/*

EXTRA_DIST = $(noinst_SCRIPTS) $(test_data)

include_HEADERS = hsync.h hsyncproto.h

bin_PROGRAMS = hsdecode hsencode hsmdfour
check_PROGRAMS = hsemit hsinhale hsfilebufcat hsmapread

test-cmds/cmds: make-cmds.py
	mkdir -p test-cmds
	$(PYTHON) $(srcdir)/make-cmds.py > $@

hsmdfour_SOURCES = hsmdfour.c mdfour.c filebuf.c fileutil.c hex.c trace.c

hsfilebufcat_SOURCES = hsfilebufcat.c filebuf.c fileutil.c trace.c netio.c

hsdecode_SOURCES = hsdecode.c
hsdecode_LDADD = libhsyncdecode.la

hsencode_SOURCES = hsencode.c
hsencode_LDADD = libhsync.la

hsemit_SOURCES = hsemit.c
hsemit_LDADD = libhsync.la

hsinhale_SOURCES = hsinhale.c
hsinhale_LDADD = libhsyncdecode.la

hsmapread_SOURCES = hsmapread.c mapptr.c filebuf.c trace.c netio.c \
	fileutil.c

# Thus spake the master programmer:
# 
# ``When the program is being tested, it is too late to make design
# changes.''

TESTS = test-mappipe.sh \
	test-mapeof.sh test-mapover.sh \
	test-md4sizes.sh test-cat.sh \
	test-mapread.sh \
	test-cmds.sh test-decode.sh test-encode.sh \
	test-thrice.sh test-seq.sh



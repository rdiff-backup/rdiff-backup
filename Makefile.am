## Process this file with automake to produce Makefile.in
## Copyright (C) 2000 by Martin Pool

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
	hex.c stats.c fileio.c 

# compress.c compress.h 

libhsyncdecode_la_SOURCES = dec.c \
	private.h netio.c includes.h \
	compress.c compress.h \
	filebuf.c membuf.c ptrbuf.c \
	inhale.c trace.c hex.c stats.c  \
	mdfour.c

noinst_SCRIPTS = test-decode.sh test-encode.sh \
	test-chain.sh test-cmds.sh \
	make-cmds.py test-thrice.sh test-seq.sh test-meta.sh \
	test-cat.sh \
	test-md4sizes.sh testfns.sh 

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


EXTRA_DIST = $(noinst_SCRIPTS) $(test_data)

include_HEADERS = hsync.h hsyncproto.h

bin_PROGRAMS = hsdecode hsencode hsmdfour
check_PROGRAMS = hsemit hsinhale hsfilebufcat

test-cmds/cmds: make-cmds.py
	mkdir -p test-cmds
	$(PYTHON) $(srcdir)/make-cmds.py > $@

hsmdfour_SOURCES = hsmdfour.c mdfour.c filebuf.c hex.c trace.c
# hsmdfour_LDADD = libhsyncdecode.la

hsfilebufcat_SOURCES = hsfilebufcat.c filebuf.c trace.c netio.c

hsdecode_SOURCES = hsdecode.c
hsdecode_LDADD = libhsyncdecode.la

hsencode_SOURCES = hsencode.c
hsencode_LDADD = libhsync.la

hsemit_SOURCES = hsemit.c
hsemit_LDADD = libhsync.la

hsinhale_SOURCES = hsinhale.c
hsinhale_LDADD = libhsyncdecode.la

# Thus spake the master programmer:
# 
# ``When the program is being tested, it is too late to make design
# changes.''

TESTS = test-md4sizes.sh test-cat.sh \
	test-cmds.sh test-decode.sh test-encode.sh \
	test-thrice.sh test-seq.sh



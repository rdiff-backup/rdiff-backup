## Process this file with automake to produce Makefile.in

CFLAGS += -W -Wall -g @trace_flags@

lib_LTLIBRARIES = libhsync.la libhsyncdecode.la

libhsync_la_SOURCES = dec.c enc.c \
	emit.h emit.c \
	litbuf.c \
	private.h netio.c includes.h \
	mdfour.c search.c \
	filebuf.c membuf.c ptrbuf.c \
	checksum.c copyq.c \
	compress.c compress.h inbuf.c 

libhsyncdecode_la_SOURCES = dec.c \
	private.h netio.c includes.h \
	compress.c compress.h \
	filebuf.c membuf.c ptrbuf.c

noinst_SCRIPTS = test-decode.sh test-encode.sh test-chain.sh

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
test-encode/01-sig

EXTRA_DIST = $(noinst_SCRIPTS) $(test_data)

include_HEADERS = hsync.h hsyncproto.h

bin_PROGRAMS = hsdecode hsencode hsemit

hsdecode_SOURCES = hsdecode.c
hsdecode_LDADD = libhsyncdecode.la

hsencode_SOURCES = hsencode.c
hsencode_LDADD = libhsync.la

hsemit_SOURCES = hsemit.c
hsemit_LDADD = libhsync.la

# Thus spake the master programmer:
# 
# ``When the program is being tested, it is too late to make design
# changes.''

TESTS = test-decode.sh test-encode.sh test-chain.sh



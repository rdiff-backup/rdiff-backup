## Process this file with automake to produce Makefile.in

CFLAGS += -W -Wall -g

lib_LTLIBRARIES = libhsync.la libhsyncdecode.la

libhsync_la_SOURCES = dec.c enc.c emit.c litbuf.c \
	private.h netio.c includes.h \
	mdfour.c mdfour.h search.c \
	filebuf.c membuf.c ptrbuf.c \
	checksum.c \
	compress.c compress.h inbuf.c

libhsyncdecode_la_SOURCES = dec.c \
	private.h netio.c includes.h \
	compress.c compress.h \
	filebuf.c membuf.c ptrbuf.c

include_HEADERS = hsync.h hsyncproto.h

bin_PROGRAMS = hsdecode hsencode

hsdecode_SOURCES = hsdecode.c
hsdecode_LDADD = libhsyncdecode.la

hsencode_SOURCES = hsencode.c
hsencode_LDADD = libhsync.la

# Thus spake the master programmer:
# 
# ``When the program is being tested, it is too late to make design
# changes.''

TESTS = test-decode.sh test-encode.sh test-chain.sh



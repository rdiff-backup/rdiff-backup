man_MANS = rdiff.1 libhsync.3

EXTRA_DIST = $(man_MANS)

%.ps: %.[0-9]
	man -Tps ./$< >$@

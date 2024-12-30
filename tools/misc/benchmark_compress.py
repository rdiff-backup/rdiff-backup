#!/usr/bin/python3
# a script to benchmark different ways to compress files
# A typical result with default values looks like this:
# $ ./tools/misc/benchmark_compress.py
# DIRECT UNBUFFERED N/A 0.17925615100011782
# DIRECT BUFFERED N/A 0.1017055429992979
# GZIP UNBUFFERED 9 0.652450399999907
# GZIP BUFFERED 9 0.35367933100042137
# BZ2 UNBUFFERED 9 15.648743923000438
# BZ2 BUFFERED 9 14.793156550000276
# LZMA UNBUFFERED 6 3.715828219999821
# LZMA BUFFERED 6 2.684497156999896
# $ ll tmp-*buffered*
# 99900 Dec 15 09:23 tmp-buffered
#   480 Dec 15 09:23 tmp-buffered.gz
#   282 Dec 15 09:24 tmp-buffered.bz2
#   248 Dec 15 09:24 tmp-buffered.xz
# 99900 Dec 15 09:23 tmp-unbuffered
#   482 Dec 15 09:23 tmp-unbuffered.gz
#   282 Dec 15 09:24 tmp-unbuffered.bz2
#   248 Dec 15 09:24 tmp-unbuffered.xz
# $ rm tmp-*buffered*

import bz2
import gzip
import lzma
import timeit

LINE = b"""alfjaw44534u8od /q389-t346b 5aop[fz89p34/ 0))({"l;346 af gtwioqwtiqtobi asgu godfi dnfiot45 89sg g.
"""
LINES = 1000
NUMBER = 1000
GZIP_COMPRESS = 9  # 0-9, default is 9
BZ2_COMPRESS = 9  # 1-9, default is 9
LZMA_PRESET = 6  # 0-9, default is 6


def write_direct_unbuffered():
    file = open("tmp-unbuffered", mode="wb")
    for i in range(0, LINES):
        file.write(LINE)
    file.close()


def write_direct_buffered():
    file = open("tmp-buffered", mode="wb")
    buffer = []
    for i in range(0, LINES):
        buffer.append(LINE)
    file.write(b"".join(buffer))
    file.close()


def write_gzip_unbuffered():
    file = gzip.GzipFile("tmp-unbuffered.gz", compresslevel=GZIP_COMPRESS, mode="wb")
    for i in range(0, LINES):
        file.write(LINE)
    file.close()


def write_gzip_buffered():
    file = gzip.GzipFile("tmp-buffered.gz", compresslevel=GZIP_COMPRESS, mode="wb")
    buffer = []
    for i in range(0, LINES):
        buffer.append(LINE)
    file.write(b"".join(buffer))
    file.close()


def write_bz2_unbuffered():
    file = bz2.BZ2File("tmp-unbuffered.bz2", mode="wb", compresslevel=BZ2_COMPRESS)
    for i in range(0, LINES):
        file.write(LINE)
    file.close()


def write_bz2_buffered():
    file = bz2.BZ2File("tmp-buffered.bz2", mode="wb", compresslevel=BZ2_COMPRESS)
    buffer = []
    for i in range(0, LINES):
        buffer.append(LINE)
    file.write(b"".join(buffer))
    file.close()


def write_lzma_unbuffered():
    file = lzma.LZMAFile("tmp-unbuffered.xz", mode="wb", preset=LZMA_PRESET)
    for i in range(0, LINES):
        file.write(LINE)
    file.close()


def write_lzma_buffered():
    file = lzma.LZMAFile("tmp-buffered.xz", mode="wb", preset=LZMA_PRESET)
    buffer = []
    for i in range(0, LINES):
        buffer.append(LINE)
    file.write(b"".join(buffer))
    file.close()


print(
    "DIRECT UNBUFFERED",
    "N/A",
    timeit.timeit(stmt="write_direct_unbuffered()", number=NUMBER, globals=globals()),
)
print(
    "DIRECT BUFFERED",
    "N/A",
    timeit.timeit(stmt="write_direct_buffered()", number=NUMBER, globals=globals()),
)

print(
    "GZIP UNBUFFERED",
    GZIP_COMPRESS,
    timeit.timeit(stmt="write_gzip_unbuffered()", number=NUMBER, globals=globals()),
)
print(
    "GZIP BUFFERED",
    GZIP_COMPRESS,
    timeit.timeit(stmt="write_gzip_buffered()", number=NUMBER, globals=globals()),
)

print(
    "BZ2 UNBUFFERED",
    BZ2_COMPRESS,
    timeit.timeit(stmt="write_bz2_unbuffered()", number=NUMBER, globals=globals()),
)
print(
    "BZ2 BUFFERED",
    BZ2_COMPRESS,
    timeit.timeit(stmt="write_bz2_buffered()", number=NUMBER, globals=globals()),
)

print(
    "LZMA UNBUFFERED",
    LZMA_PRESET,
    timeit.timeit(stmt="write_lzma_unbuffered()", number=NUMBER, globals=globals()),
)
print(
    "LZMA BUFFERED",
    LZMA_PRESET,
    timeit.timeit(stmt="write_lzma_buffered()", number=NUMBER, globals=globals()),
)

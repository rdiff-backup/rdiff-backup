# File formats {#page_formats}

## Generalities

There are two file formats used by `librsync` and `rdiff`: the
*signature* file, which summarizes a data file, and the *delta* file,
which describes the edits from one data file to another.

librsync does not know or care about any formats in the data files.

All integers are big-endian.

## Magic numbers

All librsync files start with a `uint32` magic number identifying them.
These are declared in `librsync.h`:

```
/** A delta file. At present, there's only one delta format. **/
RS_DELTA_MAGIC          = 0x72730236,      /* r s \2 6 */

/**
 * A signature file with MD4 signatures.  Backward compatible with
 * librsync < 1.0, but strongly deprecated because it creates a security
 * vulnerability on files containing partly untrusted data. See
 * <https://github.com/librsync/librsync/issues/5>.
 **/
RS_MD4_SIG_MAGIC        = 0x72730136,      /* r s \1 6 */

/**
 * A signature file using the BLAKE2 hash. Supported from librsync 1.0.
 **/
RS_BLAKE2_SIG_MAGIC     = 0x72730137       /* r s \1 7 */
```

## Signatures

Signatures consist of a header followed by a number of block
signatures.

Each block signature gives signature hashes for one block of
`block_len` bytes from the input data file. The final data block
may be shorter. The number of blocks in the signature is therefore

    ceil(input_len/block_len)

The signature header is (see `rs_sig_s_header`):

    u32 magic;     // either RS_MD4_SIG_MAGIC or RS_BLAKE2_SIG_MAGIC
    u32 block_len; // bytes per block
    u32 strong_sum_len;  // bytes per strong sum in each block

The block signature contains a rolling or weak checksum used to find
moved data, and a strong hash used to check the match is correct.
The weak checksum is computed as in `rollsum.c`. The strong hash is
either MD4 or BLAKE2 depending on the magic number.

To make the signatures smaller at a cost of a greater chance of collisions,
the `strong_sum_len` in the header can cause the strong sum to be truncated
to the left after computation.

Each signature block format is (see `rs_sig_do_block`):

    u32 weak_sum;
    u8[strong_sum_len] strong_sum;

## Delta files

Deltas consist of the delta magic constant `RS_DELTA_MAGIC` followed by a
series of commands. Commands tell the patch logic how to construct the result
file (new version) from the basis file (old version).

There are three kinds of commands: the literal command, the copy command, and
the end command. A command consists of a single byte followed by zero or more
arguments. The number and size of the arguments are defined in `prototab.c`.

A literal command describes data not present in the basis file. It has one
argument: `length`. The format is:

    u8 command; // in the range 0x41 through 0x44 inclusive
    u8[arg1_len] length;
    u8[length] data; // new data to append

A copy command describes a range of data in the basis file. It has two
arguments: `start` and `length`. The format is:

    u8 command; // in the range 0x45 through 0x54 inclusive
    u8[arg1_len] start; // offset in the basis to begin copying data
    u8[arg2_len] length; // number of bytes to copy from the basis

The end command indicates the end of the delta file. It consists of a single
null byte and has no arguments.

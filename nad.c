/* -*- mode: c; c-file-style: "bsd" -*- 
 * $Id$
 *
 * nat.c -- Generate combined signature/difference stream.
 * 
 * Copyright (C) 2000 by Martin Pool
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

#include "includes.h"
#include "hsync.h"
#include "hsyncproto.h"
#include "private.h"
#include "emit.h"

/* GENERATE NEW SIGNATURES AND DIFFERENCE STREAM

   OK, here's the deal: we hold the signatures for the cached
   instance, and we're reading the new instance from upstream.  As we
   read, we need to generate signatures for the new instance, and also
   search for blocks in it that match the old version.

   All of this has to be pipelined.  This means that we start sending
   data as soon as we can, rather than waiting until we've seen the
   whole file: it might be arbitrarily big, or take a long time to
   come down.  However, we need a certain amount of elbow-room to
   generate signatures and find matches: in fact, we need a block of
   readahead for both of them.

   It's important to understand the relationship between
   signature-generation and match-finding.  I think of them as train
   cars bumping into each other: they're both using the same map_ptr
   region and so are coupled, but they don't move in lock step.

   The block sizes for old and new signatures may be different.
   New signatures are always generated aligned on block boundaries,
   and there's no point doing rolling checksums for them, since we
   always know exactly where they're going to be.  We need to generate
   an md4sum for each block.

   In the search checksums, rolling signatures are crucially
   important, and we generate strong checksums pretty infrequently.
   If we find a match, then we need to skip over it and restart the
   rolling checksum.

   (Calculating the new and search checksums independently is a little
   inefficient when the block lengths are the same and they're
   perfectly aligned: we're calculating the signature twice for the
   same data.  Having the two files exactly the same is not uncommon,
   but still it's OK to waste a little time in this version.  We might
   in the future detect that they're the same and just echo back the
   same signature, but that's an optimization.)

   This file doesn't know about the wire encoding format: it just says
   something when it has a match, literal, or signature data, and
   emit.c et al actually send it out.

   Both the signature and search work is done from a single map_ptr
   buffer.  map_ptr does most of the intelligence about retaining and
   discarding data.  We

   There are special cases when we're approaching the end of the
   file.  The final signature must be generated over the (possibly)
   short block at the end.  The search must be prepared to match that
   short block, or if it doesn't match then to emit it as literal
   data. 

*/

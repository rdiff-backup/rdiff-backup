/*				       	-*- c-file-style: "bsd" -*-
 * rproxy -- dynamic caching and delta update in HTTP
 * $Id$
 * 
 * Copyright (C) 2000 by Martin Pool <mbp@humbug.org.au>
 * 
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public License
 * as published by the Free Software Foundation; either version 2.1 of
 * the License, or (at your option) any later version.
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


/*
 * nadnozzle: Smart, nonblocking output from nad encoding.
 *
 * The nozzle is based commands from the nad encoder.  At the moment,
 * there are five commands: COPY, LITERAL, SIGNATURE, CHECKSUM and EOF.
 * As data passes out through the nozzle, these commands can be
 * reordered or combined to produce a smaller encoding.  However, this
 * optimization only happens over a fixed-size window, and is subject
 * to certain identity constraints.
 *
 * Because the length of a command is sent at the start, we can't
 * modify commands we've already started to transmit.  Everything
 * else, however, can be mangled at will.
 *
 * `Identity constraints' just means that we want to make sure the
 * instructions we send produce the same effect as the instructions
 * passed in to us.  Therefore: COPY and LITERAL commands must be sent
 * in the same relative order they are generated.  Consecutive COPY
 * commands that refer to abutting regions of the old file may be
 * combined into a single larger command.  Consecutive LITERAL,
 * CHECKSUM and SIGNATURE commands may always be joined up.  CHECKSUM
 * commands give the checksum of the whole file to date, and so may
 * not be reordered relative to COPY and LITERAL commands.  SIGNATURE
 * commands are almost independent, but must not arrive before the
 * data they describe, although they may be delayed indefinitely.
 *
 * Therefore the only command that can be reordered is SIGNATURE which
 * may be pushed back relative to the others, although many of them
 * can be coalesced.  And in fact SIGNATURE commands will already be
 * grouped together, because the map-region code in nad encoding does
 * first search, then signature.  Therefore at the moment this code
 * does not worry too much about reordering.
 * 
 * We don't want to queue up data forever.  On each call, if we *can*
 * do output, then we should start sending whatever's next in the queue.
 *
 * To suit squid's callback mechanism, we shouldn't ever try to write
 * when we've been asked to read, or vice versa.  The encoding
 * algorithm should only write stuff into the nozzle, and then it can
 * be taken out when we next do output.
 *
 * At a certain point, we should just decide that the output queue is
 * full and that we don't want to read any more input until something
 * is written out.  Squid has the very good design that this is a
 * separate decision before trying to read, because to slow down the
 * sender we have to leave the data in the socket receive buffer in
 * the OS.  Perhaps this implies a function on the nozzle to say
 * whether it can accept any more data.
 *
 * So, there will be a public method which asks the nozzle to drain
 * itself to a particular output file.  Also, we can enquire whether
 * it's empty, full, or half-full.  The encoder has private methods
 * that enqueue particular commands.
 *
 * Literal data is not copied into the nozzle.  Rather, it's kept in
 * the input map and there's a cursor in the hs_nad_job_t which helps
 * nad retain any data that it needs to copy out.
 *
 * Does the nozzle need to actually keep a queue of things?  I kind of
 * think it does: if we have lots of input available then we will want
 * to be able to send as much output as possible next time we try.
 *
 * So the model has to be some kind of list of commands waiting to go
 * out.  As commands are appended we see if the previous command is of
 * the same type, and if so we try to coalesce them.
 *
 * When it's time to do output, we walk through the list and send each
 * command one at a time.  Commands are pulled off the queue into a
 * special slot as they're sent: we need to make sure nobody will try
 * to coalesce with them, and also if the write does not complete
 * we'll need to know how far through the command we are.  Of course
 * the write might block when we have not even begun to send out the
 * command bytes, let alone the command content.
 *
 * How do we know when the nozzle is full?  Does it matter?  Yes, I
 * think so, otherwise we might use up too much space on the server.
 * I think we should keep track of how many bytes of command body data
 * are present in the queue.  Once this gets above a certain maximum
 * we should say we're full.  The encoder ought to stop submitting
 * data after this, and the method should be publicly callable to tell
 * if input can be deferred.
 *
 * Also we need to return a special value when output is complete.  It
 * may take some time to drain the nozzle after EOF is submitted.
 */

/*
 * XXX: What will we do about sending out literals?  At the moment we
 * have the nice situation that they're sent directly from the mapptr
 * that is used for input, so they're not unnecessarily copied.  If we
 * decouple output from input like this it might be harder to keep
 * this situation: so should we block input until we're ready to
 * release it?  Perhaps it's an acceptable loss to copy them just
 * once.
 *
 * TODO: As a test case, build this thing into a filter that reads
 * commands from stdin and writes them to stdout.  In combination with
 * hsinhale and hsemit we can then test that the effect of the commands is
 * not altered.
 */

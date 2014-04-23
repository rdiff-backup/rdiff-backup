* Upload built documentation to librsync.sourcefrog.net, delete dead sites.

* Change to using SCons or some other build system?  Much easier to build
  shared libraries than
  Make, and possibly easier to build on Windows.

* Documentation
  
    Would be nice...

    Most importantly, some kind of manpage for rdiff, since it's
    closest to being an end-user tool.  After that, some API
    documentation.

    Can either persist in doing the API documentation through
    Doxygen, though I don't think it's very well suited to C
    libraries.  Perhaps it's better to just write a manpage as a
    regular document, describing the functions in the most sensible
    order.

    At the moment, reStructuredText looks like a good bet for an
    input format.

* Change existing text documentation in README.* etc to use a single
  consistant format, probably markdown.

* Version numbering: perhaps keep release numbers in sync with
  (Unix) library versions.

* Fix up consecutive matches

  We often have several consecutive matches, and we can combine them
  into a single COPY command.  So far so good.

  In some inputs, there might be several identical blocks.

  When we're matching, we want to prefer to match a block that comes
  just after the previous match, so that they'll join up nicely into
  a single larger match.  rsync does this; librsync doesn't at the
  moment.  It does cause a measurable problem.

  In fact, we could introduce an additional optimization over rsync.
  Suppose that the block A occurs twice, once followed by B and once
  by C.  When we first match it, we'll probably make an arbitrary
  choice of which one to use.  But if we next observe C, then it
  might be better to have given the offset of the A that precedes C,
  so that they can be joined into a single copy operation.

  This might be a bit complex.  You can imagine in fact needing an
  arbitrarily deep lookback.

  As a simpler optimization, we might just try to prefer matching
  blocks in the same order that they occur in the input.
  
  But for now we ought to at least check for consecutive blocks.

  On the other hand, abo says:

       In reality copy's are such a huge gain that merging them efficiently
       is a bit of a non-issue. Each copy command is only a couple of
       bytes... who cares if we output twice as many as we need to... it's
       the misses that take up whole blocks of data that people will notice.

       I believe we are already outputing consecutive blocks as a single
       "copy" command, but have you looked at the "search" code? We have far
       more serious problems with the hash-table that need to be fixed first
       :-)

       We are not getting all the hits that we could due to a limited
       hash-table, and this is going to make a much bigger difference than
       optimizing the copy commands.
  
* Optimisations and code cleanups;

  scoop.c: Scoop needs major refactor. Perhaps the API needs
  tweaking?

  rsync.h: documentation refers to rs_work(), which has been replaced
  by rs_job_iter. Vestigial rs_work_options enum typedef should be
  removed. rs_buffers_s and rs_buffers_t should be one typedef? Just
  how useful is rs_job_drive anyway? Not implemented, rs_accum_value
  Not implemented rs_mdfour_file

  patch.c: rs_patch_s_copying() does alloc, copy free, when it could
  just copy directly into rs_buffer_t buffer. This _does_ mean the
  callback can't allocate it's own data, though this can be done by
  checking if the callback changed the pointer.

  mdfour.c: This code has a different API to the RSA code in libmd
  and is coupled with librsync in unhealthy ways (trace?). Recommend
  changing to RSA API.
   
* Create library for autoconf replacement functions

  Make libreplace.a library in dir replace/ for autoconf replacement
  functions. Move snprintf.[ch] into this library. Add malloc.c, memcmp.c,
  and realloc.c functions, uncommenting checks in configure.in.
  
  Add common.h header to centralise all configure driven "#if SOMETHING"
  header variations, replacing them throughout code with #include "common.h".
  
  Make snprintf.c into two proper replacement functions for snprintf
  and vsnprintf instead of using conditional compilation.

* Don't use the rs_buffers_t structure.

  There's something confusing about the existence of this structure.
  In part it may be the name.  I think people expect that it will be
  something that behaves like a FILE* or C++ stream, and it really
  does not.  Also, the structure does not behave as an object: it's
  really just a shorthand for passing values in to the encoding
  routines, and so does not have a lot of identity of its own.

  An alternative might be

    result = rs_job_iter(job,
                         in_buf, &in_len, in_is_ending,
                         out_buf, &out_len);

  where we update the length parameters on return to show how much we
  really consumed.

  One technicality here will be to restructure the code so that the
  input buffers are passed down to the scoop/tube functions that need
  them, which are relatively deeply embedded.  I guess we could just
  stick them into the job structure, which is becoming a kind of
  catch-all "environment" for poor C programmers.

* Meta-programming

  * Plot lengths of each function

  * Some kind of statistics on delta each day

* Encoding format

  * Include a version in the signature and difference fields

  * Remember to update them if we ever ship a buggy version (nah!) so
    that other parties can know not to trust the encoded data.

* abstract encoding

  In fact, we can vary on several different variables:

    * what signature format are we using

    * what command protocol are we using

    * what search algorithm are we using?

    * what implementation version are we?

  Some are more likely to change than others.  We need a chart
  showing which source files depend on which variable.

* Error handling

  * What happens if the user terminates the request?

* Encoding implementation

  * Join up signature commands

* Encoding algorithm

  * Self-referential copy commands

    Suppose we have a file with repeating blocks.  The gdiff format
    allows for COPY commands to extend into the *output* file so that
    they can easily point this out.  By doing this, they get
    compression as well as differencing.

    It'd be pretty simple to implement this, I think: as we produce
    output, we'd also generate checksums (using the search block
    size), and add them to the sum set.  Then matches will fall out
    automatically, although we might have to specially allow for
    short blocks.

    However, I don't see many files which have repeated 1kB chunks,
    so I don't know if it would be worthwhile.

  * Extended files

    Suppose the new file just has data added to the end.  At the
    moment, we'll match everything but the last block of the old
    file.  It won't match, because at the moment the search block
    size is only reduced at the end of the *new* file.  This is a
    little inefficient, because ideally we'd know to look for the
    last block using the shortened length.

    This is a little hard to implement, though perhaps not
    impossible.  The current rolling search algorithm can only look
    for one block size at any time.  Can we do better?  Can we look
    for all block lengths that could match anything?

    Remember also that at the moment we don't send the block length
    in the signature; it's implied by the length of the new block
    that it matches.  This is kind of cute, and importantly helps
    reduce the length of the signature.

  * State-machine searching

    Building a state machine from a regular expression is a brilliant
    idea.  (I think `The Practice of Programming' walks through the
    construction of this at a fairly simple level.)

    In particular, we can search for any of a large number of
    alternatives in a very efficient way, with much less effort than
    it would take to search for each the hard way.  Remember also the
    string-searching algorithms and how much time they can take.

    I wonder if we can use similar principles here rather than the
    current simple rolling-sum mechanism?  Could it let us match
    variable-length signatures?

  * Cross-file matches

    If the downstream server had many similar URLs, it might be nice
    if it could draw on all of them as a basis.  At the moment
    there's no way to express this, and I think the work of sending
    up signatures for all of them may be too hard.

    Better just to make sure we choose the best basis if there is
    none present.  Perhaps this needs to weigh several factors.

    One factor might be that larger files are better because they're
    more likely to have a match.  I'm not sure if that's very strong,
    because they'll just bloat the request.  Another is that more
    recent files might be more useful.

* Support gzip compression of the difference stream.  Does this
  belong here, or should it be in the client and librsync just have
  an interface that lets it cleanly plug in?

  I think if we're going to just do plain gzip, rather than
  rsync-gzip, then it might as well be external.

* rsync-gzip: preload with the omitted text so as to get better
  compression.  Abo thinks this gets significantly better
  compression.  On the other hand we have to important and maintain
  our own zlib fork, at least until we can persuade the upstream to
  take the necessary patch.  Can that be done?

  abo says

       It does get better compression, but at a price. I actually
       think that getting the code to a point where a feature like
       this can be easily added or removed is more important than the
       feature itself. Having generic pre and post processing layers
       for hit/miss data would be useful. I would not like to see it
       added at all if it tangled and complicated the code.

       It also doesn't require a modified zlib... pysync uses the
       standard zlib to do it by compressing the data, then throwing
       it away. I don't know how much benefit the rsync modifications
       to zlib actually are, but if I was implementing it I would
       stick to a stock zlib until it proved significantly better to
       go with the fork.

* Licensing

  Will the GNU Lesser GPL work?  Specifically, will it be a problem
  in distributing this with Mozilla or Apache?

* Checksums

  * Do we really need to require that signatures arrive after the
    data they describe?  Does it make sense in HTTP to resume an
    interrupted transfer?

    I hope we can do this.  If we can't, however, then we should
    relax this constraint and allow signatures to arrive before the
    data they describe.  (Really?  Do we care?)

  * Allow variable-length checksums in the signature; the signature
    will have to describe the length of the sums and we must compare
    them taking this into account.

* Testing

  * Just more testing in general.

  * Perhaps merge in Comfychair into a subdirectory and use that
    rather than the shell-based scripts. There is also the C based
    "check" framework which looks nice.

  * Test broken pipes and that IO errors are handled properly.

  * Test files >2GB, >4GB.  Presumably these must be done in streams
    so that the disk requirements to run the test suite are not too
    ridiculous.  I wonder if it will take too long to run these
    tests?  Probably, but perhaps we can afford to run just one
    carefully-chosen test.

* Security audit

  * If this code was to read differences or sums from random machines
    on the network, then it's a security boundary.  Make sure that
    corrupt input data can't make the program crash or misbehave.

* Use slprintf not strnprintf, etc.

* Long files

  * How do we handle the large signatures required to support large
    files?  In particular, how do we choose an appropriate block size
    when the length is unknown?  Perhaps we should allow a way for
    the signature to scale up as it grows.

  * What do we need to do to compile in support for this?

    * On GNU, defining _LARGEFILE_SOURCE as we now do should be
      sufficient.

    * SCO and similar things on 32-bit platforms may be more
      difficult.  Some SCO systems have no 64-bit types at all, so
      there we will have to do without.

    * On larger Unix platforms we hope that large file support will
      be the default.

* Perhaps make extracted signatures still be wrapped in commands.
  What would this lead to?

  * We'd know how much signature data we expect to read, rather than
    requiring it to be terminated by the caller.


# Contributing to librsync {#page_contributing}

Instructions and conventions for people wanting to work on librsync.  Please
consider these guidelines even if you're doing your own fork.

## Code Style

The prefered style for code is equivalent to using GNU indent with the
following arguments;

```Shell
$ indent -linux -nut -i4 -ppi2 -l80 -lc80 -fc1 -fca -sob
```

The preferred style for non-docbook comments are as follows;

```C

                         /*=
                          | A short poem that
                          | shall never ever be
                          | reformated or reindented
                          */

    /* Single line comment indented to match code indenting. */

    /* Blank line delimited paragraph multi-line comments.

       Without leading stars, or blank line comment delimiters. */

    int a;                      /* code line comments */
```

The preferred style for docbook comments is javadoc with autobrief as
follows;

```C
/** \file file.c Brief summary paragraph.
  *
  * With blank line paragraph delimiters and leading stars.
  *
  * \param foo parameter descriptions...
  *
  * \param bar ...in separate blank-line delimited paragraphs.
  *
  * Example:\code
  *  code blocks that will never be reformated.
  * \endcode
  *
  * Without blank-line comment delimiters. */

    int a;                      /**< brief attribute description */
    int b;                      /**< multiline attribute description
                                 *
                                 * With blank line delimited paragraphs.*/
```

There is a `make tidy` target that will use GNU indent to reformat all
code and non-docbook comments, doing some pre/post processing with sed
to handle some corner cases indent doesn't handle well.

There is also a `make tidyc` target that will reformat all code and
comments with https://github.com/dbaarda/tidyc. This will also
correctly reformat all docbook comments, equivalent to running tidyc
with the following arguments;

```Shell
$ tidyc -R -C -l80
```

## Pull requests

Fixes or improvements in pull requests are welcome.  Please:

- [ ] Send small PRs that address one issues each.

- [ ] Update `NEWS.md` to say what you changed.

- [ ] Add a test as a self-contained C file in `tests/` that passes or fails,
  and is hooked into `CMakeLists.txt`.

- [ ] Keep the code style consistent with what's already there, especially in
  keeping symbols with an `rs_` prefix.


## NEWS

[NEWS.md](NEWS.md) contains a list of user-visible changes in the library between
releases version. This includes changes to the way it's packaged,
bug fixes, portability notes, changes to the API, and so on.

Add
and update items under a "Changes in X.Y.Z" heading at the top of
the file. Do this as you go along, so that we don't need to work
out what happened when it's time for a release.

## Tests

Please try to update docs and tests in parallel with code changes.

## Releasing

If you are making a new tarball release of librsync, follow this checklist:

* NEWS.md - make sure the top "Changes in X.Y.Z" is correct, and the date is
  correct.

* `CMakeLists.txt` - version is correct.

* `librsync.spec` - make sure version and URL are right.

* Run `make all doc check` in a clean checkout of the release tag.

Test results for builds of public github branches are at
https://travis-ci.org/librsync/librsync.

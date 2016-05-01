# Contributing to librsync {#page_contributing}

Instructions and conventions for people wanting to work on librsync.  Please
consider these guidelines even if you're doing your own fork.

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

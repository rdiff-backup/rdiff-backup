# CODING CONVENTIONS

We follow the latest flake8 enforced guidelines, but certain aspects of coding
can't be enforced through automated checks, hence to be followed by humans
and reviewers. This document lists such coding conventions.

## QUOTING

* the [style guide for Python code (PEP 8)](https://www.python.org/dev/peps/pep-0008/#string-quotes)
  doesn't recommend single vs. double quotes but states that triple-quoted
  strings should use double quotes "to be consistent with the docstring
  convention in [PEP 257](https://www.python.org/dev/peps/pep-0257)".
* for this reason, we use double quotes everywhere, unless the text contains
  itself a double quote, in which case single quotes are obviously preferred.

## PRIVATE AND PUBLIC ITEMS

* we call items any definition of class, function, member, variable, etc...
* private items are pre-fixed with an underscore
* public items are to be defined before private ones. Pre-defined functions
  (generally pre- and post-fixed with two underscores, like `__init__`) are
  defined before all others.
* the order should be logical (e.g. called functions after calling ones) rather
  than lexical.
* in class definitions, variables are defined before class methods, before
  instance methods (each in the order defined above).

## ASSERT STATEMENTS

* assert statements should be used only sparingly, and only for validating
  internal function calls. Code must continue to work with asserts disabled.
* assert statements shall not be used to validate user inputs or system
  consistency (e.g. if a backup repository is corrupt or not).
* all used assert statements must have an explanatory text. It should explain
  _why_ it went wrong rather than the test result itself.
* longer assert statements use parentheses and not backslashes to go over
  multiple lines, e.g. `assert (condition), ("text {hold}".format(hold=var))`.
* assert messages should only appear during coding, assert messages visible
  to users are candidate for replacement through a proper fatal error handling.
* assert messages might not need translation in the future, as they shouldn't
  be seen by users, but still follow the "TEXT OUTPUT" conventions.

## TEXT OUTPUT

* any text output should start with a capital letter and end with a dot.
* text output with variables is formatted with named placeholders using the
  form `"Some error message regarding '{xyz}'.".format(xyz=actual_var)`.
* complex placeholders should be kept between single quotes in the string.
* name of placeholders should be short, unique, meaningful, only using letters
  (with an optional counter at the end) and not be named after existing
  functions or keywords. Examples:
    * `{itype}` instead of `{type}` or `{increment_type}`
    * `"The two types '{type1}' and '{type2}' are different.".format(...)`
* use `{rp!s}` (or similar name) for the representation of RPath/RORPath in
  order to enforce complete path representation (it is somewhat equivalent to
  `str(rp)`).
* each text string should be a one-liner and leave formatting to the `log.Log`
  class.
  TODO: the code isn't yet that far but it should be the direction.
* the explanation should be meant first for the user, and explain ways to solve
  the potential issue, then for the developer to troubleshoot.

> **NOTE:** one of the main driver for the above recommendations is the
	possibility to translate those strings in the future.

## BYTES VS. STR

* Paths and commands are expressed in bytes to avoid issues with cross-platform
  encoding conversion, any function manipulating such things must return bytes.
* Only methods creating a Path/Command object (`__init__` and similar) might
  accept strings as input and convert them internally to bytes. Other functions
  must make sure that they don't accept strings as input (this is one of the
  few reasons to use asserts).
* Any conversion between strings and bytes happens with `os.fsencode/fsdecode`.
* Messages are to be expressed in strings (log, errors, etc).

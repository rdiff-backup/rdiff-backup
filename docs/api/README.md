# client/server API documentation

It is important that the API between two versions of rdiff-backup run in
client/server mode remains stable, so that an upgrade doesn't need to be done
on both sides at the same time, as some of our users have sizable
installations.

## API version files

Each version file named vX.Y.md lists the objects and functions or methods
defining the API interfaces. A basis version can be created using the script
`tools/prepare_api_doc.sh` but it needs to be improved respecting the
following structure:

* _Format_ contains changes at the communication format as a bulleted
  list of free text describing the changes.
* _Sources_ contains the analysis of the actual source files under `src`
* _Testing_ contains the interfaces used by the test files. These don't require
  to be stable and are present mostly for reference.

We also make the difference between `internal` and `external` interfaces:

* _Internal_ are defined in the rdiff-backup modules and are under control of
  the programmer, and must respect the rules edicted later.

* _External_ are defined in Python and 3rd party libraries, they are
  rather independent of the programmer of rdiff-backup but more of the
  system on each side of the connection, python version installed. This can
  help to assess which version of Python can be supported. It must follow
  similar rules to deprecated and new interfaces e.g. so that users can upgrade
  their python version timely.

> **CAUTION:** the functions defined in `connection.py` don't have a module
	prefix like all the other internal interfaces.
	Make sure that you don't mix them up with the external interfaces.

Each API version has its own file so that different versions can be easily
compared. For this reason it is important to keep a consistent format and
ordering, including blank lines and formatting.

Each interface is described on a separate line of the following formats,
`<module>` being optional:

```
* `<module>.<interface>`
* `<module>.<interface>` **new**
* `<module>.<interface>` **deprecated**
```

## Rules and conventions

* each call in the code through the connection must be done in the form of
  `conn.<module>.<interface>` so that the code analysis can be successful.
  The connection variable name only needs to _end_ in `conn` (e.g.
  `client_conn` is also fine).
* avoid using the above construct in comments to not have false positives,
  use e.g. `connX.<module>.<interface>` to avoid this.
* interfaces defined in `connect.py` should be named `conn_<interface>` to
  compensate for the lack of module prefix.
* a new interface is marked as **new** for _at least_ one minor version of the
  API. In these versions, the new interface can't be used to guarantee backward
  compatibility, unless a (yet to be defined) command line parameter allows it.
* a deprecated interface is marked as **deprecated** for _at least_ one minor
  version of the API.
* to keep things simple, it is forbidden to modify an existing interface
  (e.g. add or remove parameters to a function). In such cases, add a new
  function and deprecate the old function.
* a new major version of the API is declared once:
    * a **deprecated** interface is being definitely removed,
    * or a **new** interface given free for usage.
    * any incompatible change of the communication format, e.g. pickle format.
* there must be at least one _application_ version between two increases of
  the API major version, so that upgrades can be done for clients and servers
  independently. Application bug-fix versions do _not_ count in this rule.
* API and application don't need to be aligned, else we wouldn't need to
  consider separate versioning schemes.

> **NOTE:** we consider v1.0 the implicit API version of the 1.y application
	version and v2.0 the de-facto API version of the 2.0.z application
	versions. The interfaces of both API versions don't differ, they
	are still incompatible due to changes between Python 2 and 3.

## Example

To make the above rules more concrete:

Version 15.0.0 of rdiff-backup uses version 5.0 of the API and has 2 interfaces:

* `deepen`
* `unchain`

A version 5.1 of the API is created with a new function `neglect` and making
`deepen` deprecated:

* `deepen` **deprecated**
* `neglect` **new**
* `unchain`

At least one version of rdiff-backup must use the new API version, say 15.1.0.
A version 15.0.1 wouldn't be sufficient (and it isn't expected or recommended
to change API version in a bug-fix version). Version 15.1.0 defines the
`neglect` function but does _not_ use it by default (unless a flag enforces
its use, it could be simply a new command line option).
Version 15.1.0 works hence by default with version 15.0.0.

A version 5.2 of the API could be created, with other changes, but the
new resp. deprecated states wouldn't change:

* `deepen` **deprecated**
* `neglect` **new**
* `unchain`

A version 6.0 of the API can then be created, which removes the deprecated
interface and makes the new interface usable by default:

* `neglect`
* `unchain`

This version 6.0 could then be used by a new version of rdiff-backup 15.2.0,
which would work with version 15.1.0 but not with version 15.0.0.

> **NOTE:** we could declare a version 16.0.0 but that shouldn't be necessary
	and should more depend on the importance of the changes rather than
	on individual interface changes.

> **NOTE:** the `--version` option should long term also output the API
	version(s) supported and the correct one be agreed automatically.

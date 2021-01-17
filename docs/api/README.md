# client/server API documentation

It is important that the API between two versions of rdiff-backup run in
client/server mode remains stable, so that an upgrade doesn't need to be done
on both sides at the same time, as some of our users have sizable
installations.

## API version files

Each version file named vXYY.md lists the objects and functions or methods
defining the API interfaces for the major version X, minor version YY.
We use an integer instead of a traditional version scheme to make comparaisons
easier internally, and avoid confusion with the application's version.

A basis version of the file can be created using the script
`tools/prepare_api_doc.sh` but it needs to be improved manually respecting
the following structure:

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

## Mark in code

In order to simplify identification of API elements while coding, each element
is marked in the code according to the following pattern. Each
of the API parameters is the API version with which the element has been
respectively added, deprecated or removed:

```
# @API(interface_name, min_api, deprecated_api=None, obsolete_api=None)
```

As an example the minimum syntax should look like as follows for a function
which hasn't yet been deprecated:

```
# @API(my_interface_function, 200)
def my_interface_function(param1, param2, ...)
    """ [... etc ...] """
```

Once deprecated with API 212, the same function would look as follows:

```
# @API(my_interface_function, 200, 212)
def my_interface_function(param1, param2, ...)
    """ [... etc ...] """
```

> **NOTE:** the syntax is very similar to decorators, which could be an option
	in the future, but wouldn't apply to classes and variables, and for
	which no added value has been yet identified (with potential
	performance impact). Important is that it remains easy to detect and
	parse automatically to simplify future evolutions.

Functions created in order to guarantee compatibility with an older API version
are to be named `_compatNNN`, e.g. `_compat200`, so that it is clear that they
can be removed once the API version isn't supported any more.

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
* there must be at least one _application_ major version between two increases
  of the API major version, so that upgrades can be done for clients and servers
  independently.
* we strive to have at least one year, better more, between major releases to
  give enough time for upgrades of big installations. Development constraints
  might require faster cycles, but those should be avoided with time.
* API and application don't need to be aligned, else we wouldn't need to
  consider separate versioning schemes, but it makes things simpler when major
  versions are aligned. Important changes not impacting the interface, e.g. to
  the repository format, might nevertheless govern the introduction of an
  application major version, independently of any breaking change to the API.

> **NOTE:** we consider v100 the implicit API version of the 1.y application
	version and v200 the de-facto API version of the 2.0.z application
	versions. The interfaces of both API versions don't differ, they
	are still incompatible due to changes between Python 2 and 3.

## Example

To make the above rules more concrete:

Version 5.0.0 of rdiff-backup uses version 500 of the API and has 2 interfaces:

* `deepen`
* `unchain`

A version 501 of the API is created with a new function `neglect` and making
`deepen` deprecated:

* `deepen` **deprecated**
* `neglect` **new**
* `unchain`

At least one version of rdiff-backup must use the new API version, say 5.1.0.
A version 5.0.1 wouldn't be sufficient (and it isn't expected or recommended
to change API version in a bug-fix version). Version 5.1.0 defines the
`neglect` function but does _not_ use it by default (unless a flag enforces
its use, it could be simply a new command line option).
Version 5.1.0 works hence by default with version 5.0.0.

A version 502 of the API could be created, with other changes, but the
new resp. deprecated states wouldn't change:

* `deepen` **deprecated**
* `neglect` **new**
* `unchain`

A version 600 of the API can then be created, which removes the deprecated
interface and makes the new interface usable by default:

* `neglect`
* `unchain`

This version 600 could then be used by a new version of rdiff-backup 6.0.0,
which would work with version 5.1.0 but not with version 5.0.z.

> **NOTE:** it could be as well a version 7.0.0 should other important changes
	have justified a major version in-between.

> **NOTE:** the `--version` option should long term also output the API
	version(s) supported and the correct one be agreed automatically.

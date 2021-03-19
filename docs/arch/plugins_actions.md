# RDIFF-BACKUP ACTIONS PLUGINS

## Naming convention and actions manager

An action plug-in is:

1. either in the `rdiffbackup.actions` namespace, with any module name (this is
   how built-in action modules are packaged),
2. or a top-level module with a name `rdb_action_[...].py`

All those plug-ins are found by the action manager module
`rdiffbackup.actions_mgr` and returned as a hash made of key-value pairs by the function `get_discovered_actions`:

* key is the name returned by the Action class (see below the `get_name` method)
* value is the Action class itself, as returned by the `get_action_class`
  function of the action plug-in module.

> **NOTE:** more information is provided with `pydoc rdiffbackup.actions_mgr`.

The actions manager also has two functions to get lists of argparse parsers
to use with `arguments.parse`, `get_generic_parsers` for generic parsers
common to all actions, and `get_parent_parsers_compat200` to get all
parsers of all "traditional" actions, for faking the old CLI.

## Module interface

Each action plug-in module contains one single Action-class. This action class
is returned by the function `get_action_class` of the module. How the action
class is named and of which hierarchy it descends is irrelevant (though it
makes sense to derive it from the rdiffbackup.actions.BaseAction class).

All further action plug-in interactions are executed through the interface of
this single class.

## Action class interface

The Action class has the following interface:

* the class method `cls.get_name()` returns the name of the plug-in, only this
  name will be used in the code, and it doesn't need to be aligned with the name
  of the module or of the class (but it should). Only requirement is that it is
  unique or plug-ins will overwrite each other.
* the class method `cls.get_security_class()` returns the security class of
  the action plug-in, one of `backup`, `restore` or `validate`.
* the class method `cls.get_version()` returns the version of the plug-in as a
  string.
* the class method `cls.add_action_subparser(sub_handler)` returns a subparser
  as returned by argparse's `sub_handler.add_parser` function, so that the
  sub-options of the action can be parsed by the `rdiffbackup.arguments.parse`
  function.
* the method `self.__init__(args, log, errlog)` initializes the class as object,
  based on the namespace returned by argparse, a Log and an ErrorLog object.
* the method `self.pre_check()` just validates that the arguments passed were
  correct, beyond what argparse could do, and shouldn't try to connect yet to
  any remote location. A return value unequal 0 means an error, which can be
  used as exit code.
* the method `self.connect()` returns a
  [context manager object](https://docs.python.org/3/reference/datamodel.html#with-statement-context-managers)
  which can be used in a `with action.connect() as conn_act:` construct.
  It is expected that the action object itself is the context manager, but it
  isn't absolutely necessary (but the default implementation offered by the
  BaseAction). The returned class must hence have two methods `self.__enter__()`
  and `self.__exit__(self, exc_type, exc_value, traceback)` (closing the
  connections). Again, it is expected that the runtime context object returned
  by `__enter__` is the same action object (aka `return self`), but it isn't
  an obligation.

  This context object has the following interface, usable through the
  connection(s) started by `connect()`:
    * `self.check()` to validate the environment before doing _any_ changes.
      The check method continues to verify the environment and report as many issues as it can, as to help the user to fix them at once.
      It returns 0 in case of success, else an integer to be used as exit code.
    * `self.setup()` prepares the environment (define variables, etc), it might create empty directories and logfiles, but it can't lead under any circumstances to a broken repository requiring a regression.
      The setup method returns as soon as it finds an issue and doesn't try to continue.
      It returns 0 in case of success, else an integer to be used as exit code.
    * `self.run()` finally does whatever the action is supposed to do.
      It might return 0 in case of success, else an integer to be used as exit
      code. It is the only function that might exit directly instead, even
      though it isn't the recommended approach (but a matter of fact for most
      existing actions).

> **NOTE:** the context object doesn't need a "cleanup" action as clean-up is to
  be done as part of the `__exit__` method provided by the context manager.

Of course, action classes inheriting from the BaseAction class don't need to define all aspects themselves, making the life of plug-in developers easier.

> **NOTE:** more information is provided with `pydoc rdiffbackup.actions`.

## Pseudo-code

Taking all together, the code to use an action plugin would look as follows,
without any error handling:

```
discovered_actions = actions_mgr.get_discovered_actions()
parsed_args = arguments.parse(
	arglist, "rdiff-backup {ver}".format(ver=Globals.version),
	actions_mgr.get_generic_parsers(),
	actions_mgr.get_parent_parsers_compat200(),
	discovered_actions)
action = discovered_actions[parsed_args.action](parsed_args, Log, ErrorLog)
action.pre_check()
# implicit context_manager.__enter__()
with action.connect() as conn_act:
	conn_act.check()
	conn_act.setup()
	conn_act.run()
# implicit context_manager.__exit__(exc_type, exc_val, exc_tb)
```

> **TIP:** the actual code can be found in `rdiff_backup.Main._main_run()`.

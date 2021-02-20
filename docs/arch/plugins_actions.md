# RDIFF-BACKUP ACTIONS PLUGINS

## Naming convention and actions manager

An action plug-in is:

1. either in the `rdiffbackup.actions` namespace, with any module name (this is
   how built-in action modules are packaged),
2. or a top-level module with a name `rdb_action_[...].py`

All those plug-ins are found by the action manager module `rdiffbackup.actions_mgr`
and returned as a hash made of key-value pairs by the function `get_discovered_actions`:

* key is the name returned by the Action class (see below the `get_name` method)
* value is the Action class itself, as returned by the `get_action_class` function
  of the action plug-in module.

> **NOTE:** more information is provided with `pydoc rdiffbackup.actions_mgr`.

## Module interface

Each action plug-in module contains one single Action-class. This action class is
returned by the function `get_action_class` of the module. How the action class is
named and of which hierarchy it descends is irrelevant (though it makes sense to
derive it from the rdiffbackup.actions.BaseAction class).

All further action plug-in interactions are executed through the interface of
this single class.

## Action class interface

The Action class has the following interface:

* the class method `cls.get_name()` returns the name of the plug-in, only this name
  will be used in the code, and it doesn't need to be aligned with the name of
  the module or of the class (but it should). Only requirement is that it is
  unique or plug-ins will overwrite each other.
* the class method `cls.get_version()` returns the version of the plug-in as a string.
* the class method `cls.add_action_subparser(sub_handler)` returns a subparser as
  returned by argparse's `sub_handler.add_parser` function, so that the sub-options
  of the action can be parsed by the `rdiffbackup.arguments.parse` function.

> **TODO:** further interface aspects haven't yet been defined but will definitely be
  added step by step as the code progress. The current direction is to have the class
  being instantiated from the Namespace resulting of the parsing of the CLI arguments,
  and then object methods representing a workflow through the action be called one after
  the other, something like:
  `pre_check` → `connect` → `execute` → `clean_up`.

Of course, action classes inheriting from the BaseAction class don't need to define all
aspects themselves, making the life of plug-in developers easier.

> **NOTE:** more information is provided with `pydoc rdiffbackup.actions`.

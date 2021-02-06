'''
rdiff-backup Actions Manager - a module to discover and return built-in and
3rd party plugins for actions (used on the command line), like backup or
restore.
'''

import importlib
import pkgutil

import rdiffbackup.actions


def get_discovered_actions():
    '''
    Discover all rdiff-backup actions, either from the 'rdiffbackup.actions'
    spacename, or top-level modules with a name starting with 'rdb_action_'.
    Returns a dictionary with the name of each Action-class as key, and
    the class returned by get_action_class() as value.
    '''
    # we discover first potential 3rd party plugins, based on name
    discovered_action_plugins = {
        name: importlib.import_module(name)
        for finder, name, ispkg
        in pkgutil.iter_modules()
        if name.startswith('rdb_action_')
    }
    # and we complete/overwrite with modules delivered in the namespace
    discovered_action_plugins.update({
        name: importlib.import_module(name)
        for finder, name, ispkg
        in _iter_namespace(rdiffbackup.actions)
    })
    # then we create the dictionary of {action_name: ActionClass}
    actions = {
        action.get_action_class().get_name(): action.get_action_class()
        for action
        in discovered_action_plugins.values()
    }
    return actions


def get_generic_parsers():
    return rdiffbackup.actions.GENERIC_PARSERS


def get_parent_parsers():
    return rdiffbackup.actions.PARENT_PARSERS


def _iter_namespace(nsp):
    '''
    Return an iterator of names of modules found in a specific namespace.
    The names are made absolute, with the namespace as prefix, to simplify
    import.
    '''
    # Specifying the second argument (prefix) to iter_modules makes the
    # returned name an absolute name instead of a relative one. This allows
    # import_module to work without having to do additional modification to
    # the name.
    return pkgutil.iter_modules(nsp.__path__, nsp.__name__ + '.')


if __name__ == '__main__':
    actions = get_discovered_actions()
    for name, action_class in actions.items():
        print(name + ': ' + action_class.get_version())

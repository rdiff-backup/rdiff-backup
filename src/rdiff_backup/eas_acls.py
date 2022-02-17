# compat200
"""
Wrapper for the acl_posix.AccessControlLists and ea.ExtendedAttributes classes,
required for compatibility with API < 201

This is required because those objects are transferred implicitly
through the connection.
"""

from rdiffbackup.meta import acl_posix, ea


class AccessControlLists(acl_posix.AccessControlLists):
    pass


class ExtendedAttributes(ea.ExtendedAttributes):
    pass

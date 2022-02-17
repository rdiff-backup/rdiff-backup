# compat200
"""
Wrapper for the acl_win.ACL class, required for compatibility with API < 201

This is required because the Windows ACL object is transferred implicitly
through the connection.
"""

from rdiffbackup.meta import acl_win


class ACL(acl_win.ACL):
    pass

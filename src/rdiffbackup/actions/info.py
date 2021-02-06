
from rdiffbackup.actions import BaseAction


class InfoAction(BaseAction):
    """
    Output information about the current system, so that it can be used in
    in a bug report, and exits.
    """
    name = "info"
    # information has no specific sub-options


def get_action_class():
    return InfoAction

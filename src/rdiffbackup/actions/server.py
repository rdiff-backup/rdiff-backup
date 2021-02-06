
from rdiffbackup.actions import BaseAction


class ServerAction(BaseAction):
    """
    Start rdiff-backup in server mode (only meant for internal use).
    """
    name = "server"
    # server has no specific sub-options


def get_action_class():
    return ServerAction

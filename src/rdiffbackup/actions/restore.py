
from rdiffbackup.actions import (
    BaseAction,
    CREATION_PARSER, COMPRESSION_PARSER, SELECTION_PARSER,
    FILESYSTEM_PARSER, USER_GROUP_PARSER,
)


class RestoreAction(BaseAction):
    """
    Restore a backup at a given time (default is latest) from a repository
    to a target directory.
    """
    name = "restore"
    parent_parsers = [
        CREATION_PARSER, COMPRESSION_PARSER, SELECTION_PARSER,
        FILESYSTEM_PARSER, USER_GROUP_PARSER,
    ]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        restore_group = subparser.add_mutually_exclusive_group()
        restore_group.add_argument(
            "--at", metavar="TIME",
            help="restore files as of a specific time")
        restore_group.add_argument(
            "--increment", action="store_true",
            help="restore from a specific increment as first parameter")
        subparser.add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=2,
            help="locations of backup REPOSITORY/INCREMENT and to which TARGET_DIR to restore")
        return subparser


def get_action_class():
    return RestoreAction

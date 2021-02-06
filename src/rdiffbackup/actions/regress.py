
from rdiffbackup.actions import (
    BaseAction,
    COMPRESSION_PARSER, TIMESTAMP_PARSER, USER_GROUP_PARSER,
)


class RegressAction(BaseAction):
    """
    Regress a backup repository, i.e. remove the last (failed) incremental
    backup and reverse to the last known good mirror.
    """
    name = "regress"
    parent_parsers = [COMPRESSION_PARSER, TIMESTAMP_PARSER, USER_GROUP_PARSER]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=1,
            help="location of repository to check and possibly regress")
        return subparser


def get_action_class():
    return RegressAction

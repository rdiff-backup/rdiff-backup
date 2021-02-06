
from rdiffbackup.actions import (
    BaseAction,
    SELECTION_PARSER,
)


class CompareAction(BaseAction):
    """
    Compare the content of a source directory with a backup repository
    at a given time, using multiple methods.
    """
    name = "compare"
    parent_parsers = [SELECTION_PARSER]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "--method", choices=["meta", "full", "hash"], default="meta",
            help="use metadata, complete file or hash to compare directories")
        subparser.add_argument(
            "--at", metavar="TIME", default="now",
            help="compare with the backup at the given time, default is 'now'")
        subparser.add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=2,
            help="locations of SOURCE_DIR and backup REPOSITORY to compare"
                 " (same order as for a backup)")
        return subparser


def get_action_class():
    return CompareAction

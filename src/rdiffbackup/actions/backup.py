from rdiffbackup.actions import (
    BaseAction,
    CREATION_PARSER, COMPRESSION_PARSER, SELECTION_PARSER,
    FILESYSTEM_PARSER, USER_GROUP_PARSER, STATISTICS_PARSER,
)


class BackupAction(BaseAction):
    """
    Backup a source directory to a target backup repository.
    """
    name = "backup"
    parent_parsers = [
        CREATION_PARSER, COMPRESSION_PARSER, SELECTION_PARSER,
        FILESYSTEM_PARSER, USER_GROUP_PARSER, STATISTICS_PARSER,
    ]

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=2,
            help="locations of SOURCE_DIR and to which REPOSITORY to backup")
        return subparser


def get_action_class():
    return BackupAction

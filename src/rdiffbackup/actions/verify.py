
from rdiffbackup.actions import BaseAction


class VerifyAction(BaseAction):
    """
    Verify that files in a backup repository correspond to their stored hash,
    or that servers are properly reachable.
    """
    name = "verify"

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        entity_parsers = cls._get_subparsers(
            subparser, "entity", "files", "servers")
        entity_parsers["files"].add_argument(
            "--at", metavar="TIME", default="now",
            help="as of which time to check the files' hashes (default is now/latest)")
        entity_parsers["files"].add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs=1,
            help="location of repository where to check files' hashes")
        entity_parsers["servers"].add_argument(
            "locations", metavar="[[USER@]SERVER::]PATH", nargs="+",
            help="location of remote repositories to check for connection")
        return subparser


def get_action_class():
    return VerifyAction

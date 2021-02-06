
from rdiffbackup.actions import BaseAction


class CalculateAction(BaseAction):
    """
    Calculate values (average by default) across multiple statistics files.
    """
    name = "calculate"

    @classmethod
    def add_action_subparser(cls, sub_handler):
        subparser = super().add_action_subparser(sub_handler)
        subparser.add_argument(
            "--method", choices=["average"], default="average",
            help="what to calculate from the different statistics")
        subparser.add_argument(
            "locations", metavar="STATISTIC_FILE", nargs="+",
            help="locations of the statistic files to calculate from")
        return subparser


def get_action_class():
    return CalculateAction

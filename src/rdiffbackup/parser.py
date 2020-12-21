import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="local/remote mirror and incremental backup")
    parser.add_argument("-v", "--verbose", type=int, default=3, choices=range(1,10)
                        help="Set the verbosity from 1 (low) to 9 (debug)")
    parser.add_argument("--current-time", type=int, help="fake the current time instead of using the real one")
    parser.add_argument(
        "--force", action='store_true', default=False,
        help="enforces certain risky behaviors, like overwriting existing files, use with care!")

    subparsers = parser.add_subparsers(title='actions', help='sub-command help')

    parsers = {}

    parsers['backup'] = subparsers.add_parser('backup')
    parsers['backup'].set_defaults(action='backup')

    parsers['calculate-average'] = subparsers.add_parser('calculate-average', aliases=['ca'])
    parsers['calculate-average'].set_defaults(action='calculate-average')

    parsers['check-destination-dir'] = subparsers.add_parser('check-destination-dir', aliases=['cdd'])
    parsers['check-destination-dir'].set_defaults(action='check-destination-dir')
    parsers['check-destination-dir'].add_argument(
            '--allow-duplicate-timestamps',
            action='store_true', default=False,
            help='use this option only if you encounter duplicate metadata mirrors')

    parsers['compare'] = subparsers.add_parser('compare')
    parsers['compare'].set_defaults(action='compare')
    parsers['compare'].add_argument(
            '--method',
            type=str, default='meta', choices=["meta","full","hash"],
            help="use metadata, complete file or hash to compare directories")
    parsers['compare'].add_argument(
            '--at-time',
            type=str, default='now',
            help="compare with the backup at the given time, default is 'now'")

    parsers['list'] = subparsers.add_parser('list')
    parsers['list'].set_defaults(action='list')
    # at-time, changed-since, increments, increment-sizes [repo] [subdir]

    # --carbonfile Enable backup of MacOS X carbonfile information.
    # --create-full-path
    # --group-mapping-file

    # PARENT: --exclude... --include... --max-file-size --min-file-size

    args = parser.parse_args()
    return args

if __name__ == "__main__":
    print(parse_arguments())

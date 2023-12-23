#!/usr/bin/env python
# Alternative using the build front-end to `python -m setuptools_scm`

import argparse
import pathlib

import build.util


def get_args():
    """Parse the command line arguments"""
    args_parser = argparse.ArgumentParser(
        description="Output some or all metadata of a given project"
    )
    args_parser.add_argument(
        "--path",
        "-p",
        default=".",
        help="Path where to find the project (default: current path)",
    )
    args_parser.add_argument(
        "keys", nargs="*", help="Metadata keys to output (else output all metadata)"
    )
    args = args_parser.parse_args()
    return args


def get_metadata(path="."):
    """Get project metadata from the given path"""
    path = pathlib.Path(path)
    try:
        metadata = build.util.project_wheel_metadata(path, isolated=False)
    except build.BuildBackendException:
        metadata = build.util.project_wheel_metadata(path, isolated=True)
    return metadata


def main():
    args = get_args()

    metadata = get_metadata(args.path)

    if args.keys:
        for key in args.keys:
            print(metadata[key])
    else:
        print(metadata)


if __name__ == "__main__":
    main()

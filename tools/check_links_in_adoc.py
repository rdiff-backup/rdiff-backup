#!/usr/bin/env python3
# Check links in given asciidoctor files
# e.g. `tools/check_links_in_adoc.py $(find docs -name \*.adoc) *.adoc`

import argparse
import io
import os
import re
import requests  # type: ignore
import sys
from typing import List, Tuple

# a regular expression matching links in Asciidoc
ADOC_LINKS = re.compile(r'(?:\W|^)(?:(?:link:|image::?|include::|xref:)([^[]+)\[|((?:ht|f)tps?://[^[]*)\[|link="?([^]"]+)"?\])')
LINK_REMOTE = re.compile('(ht|f)tps?://')


class Link():
    uri: str
    file: str
    line: int
    type: str

    def __init__(self, uri: str, file: str, line: int):
        self.uri = uri
        self.file = file
        self.line = line
        if uri.startswith('http://') or uri.startswith('https://'):
            self.type = 'url'
        elif uri.startswith('http://') or uri.startswith('https://'):
            self.type = 'ftp'
        elif uri.startswith('mailto:'):
            self.type = 'email'
        else:
            self.type = 'path'


def parse_args(args: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Check URLs in asciidoctor files')
    parser.add_argument('--verbose', '-v', action='store_const',
                        const=True, default=False,
                        help='Output all found links, not only failed ones')
    parser.add_argument('--timeout', '-t', type=int, default=2,
                        help='Timeout in seconds (default 2)')
    parser.add_argument('adoc', type=argparse.FileType('r'), nargs='+',
                        help='Names of asciidoctor files')
    return parser.parse_args(args)


def extract_links(adoc: io.TextIOWrapper) -> Tuple[int, List[Link]]:
    links = []
    line_nr = 1
    for line in adoc:
        line = line.strip()
        for match in ADOC_LINKS.finditer(line):
            if match:
                for link in match.groups():
                    if link:
                        links.append(Link(link, str(adoc.name), line_nr))
        line_nr += 1
    return 0, links


def check_link(link: Link) -> int:
    if link.type == 'url':
        return check_link_url(link)
    elif link.type == 'path':
        return check_link_path(link)
    else:
        return 0  # ignored


def check_link_url(link: Link) -> int:
    try:
        rc = requests.head(link.uri, timeout=2, allow_redirects=True)
    except (requests.ConnectionError,
            requests.exceptions.ReadTimeout) as exc:
        fail(link, exc)
        return 2
    if rc.status_code == 200:
        ok(link)
        return 0
    else:
        fail(link, rc.status_code)
        return 4


def check_link_path(link: Link) -> int:
    if os.path.isabs(link.uri):
        fullname = link.uri
    else:
        dirname = os.path.dirname(link.file)
        fullname = os.path.join(dirname, link.uri)
    if os.path.exists(fullname):
        ok(link)
        return 0
    else:
        fail(link, 'NoFile ' + fullname)
        return 1


def fail(link: Link, reason: str) -> None:
    prefix = link.type.upper() + ':'
    print(prefix, link.file, link.line, link.uri, '[FAIL - {}]'.format(reason))


def ok(link: Link) -> None:
    if values.verbose:
        prefix = link.type.upper() + ':'
        print(prefix, link.file, link.line, link.uri, '[OK]')


if __name__ == '__main__':
    values = parse_args(sys.argv[1:])
    ret_code = 0
    all_links = []
    for adoc in values.adoc:
        rc, links = extract_links(adoc)
        ret_code |= rc
        all_links += links
    if ret_code:
        sys.exit(ret_code)
    for link in all_links:
        ret_code |= check_link(link)
    sys.exit(ret_code)

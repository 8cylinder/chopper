#!/usr/bin/env python3

from datetime import datetime
import os
import errno
import re
import argparse
import textwrap
from pprint import pprint as pp
# import logging
from html.parser import HTMLParser
from pathlib import Path
import textwrap

NOW = datetime.now().isoformat()

# logger = logging.getLogger(__name__)
# click_log.basic_config(logger)


class HTMLParser(HTMLParser):
    tags = ['style', 'script', 'chop']
    current_tag = None
    path = None
    parsed_data = []

    def handle_starttag(self, tag, attrs):
        self.current_tag = None
        self.path = None
        if tag in self.tags:
            for attr in attrs:
                if attr[0] == 'chopper:file':
                    self.current_tag = tag
                    self.path = attr[1]

    def handle_endtag(self, tag):
        self.current_tag = None
        self.path = None
        if tag in self.tags:
            self.parsed_data[-1]['end'] = self.getpos()[0] - 1

    def handle_data(self, data):
        if self.current_tag in self.tags:
            self.parsed_data.append({
                'path': self.path,
                'tag': self.current_tag,
                'start': self.getpos()[0],
            })


def find_chopper_files(source):
    if not os.path.exists(source):
        raise FileNotFoundError(
            errno.ENOENT, os.strerror(errno.ENOENT), source)

    if not os.path.isdir(source):
        raise NotADirectoryError(
            errno.ENOTDIR, os.strerror(errno.ENOTDIR), source)

    chopper_files = []

    for root, dirs, files in os.walk(source):
        for filename in files:
            if filename.endswith(".chopper.html"):
                chopper_files.append(os.path.join(root, filename))

    return chopper_files


def chop(source, types):
    print(source)
    with open(source, 'r') as f:
        source_html = f.read()

    parser = HTMLParser()
    parser.feed(source_html)
    data = parser.parsed_data

    source_html = source_html.splitlines()
    for block in data:
        content = source_html[block['start']:block['end']]
        content = '\n'.join(content)
        content = textwrap.dedent(content)
        block['content'] = content
        block['base_path'] = types[block['tag']]
        make_file(block)


def make_file(block):
    # pp(block)
    partial = Path(os.path.join(block['base_path'], block['path']))

    if partial.parent.mkdir(parents=True, exist_ok=True):
        print(f'chopper: made dir, {partial.parent}')

    if partial.write_text(block['content']):
        print(f'chopper: wrote to {partial}')


def main():
    help_msg = textwrap.dedent('''
      Chop files into their seperate types, style, script and html.

      Get to the choppa!
    ''')

    parser = argparse.ArgumentParser(
        description=help_msg,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        '-s', '--script-dir',
        help='Destination for the script files')
    parser.add_argument(
        '-c', '--style-dir',
        help='Destination for the style files')
    parser.add_argument(
        '-m', '--html-dir',
        help='Destination for the html files')
    parser.add_argument(
        '--comments',
        action="store_true",
        help='Add comments to generated files')
    parser.add_argument(
        'source_dir',
        metavar='SOURCE-DIR',
        help='The directory that contains the chopper files.')

    args = parser.parse_args()

    chopper_files = find_chopper_files(args.source_dir)
    types = {
        'script': args.script_dir or '',
        'style': args.style_dir or '',
        'chop': args.html_dir or '',
    }
    for source in chopper_files:
        chop(source, types)

    # pp(args)
    # pp(args.source_dir)


if __name__ == '__main__':
    main()

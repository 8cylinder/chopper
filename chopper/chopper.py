#!/usr/bin/env python3

from datetime import datetime
import os
import sys
import errno
import re
import argparse
import textwrap
from pprint import pprint as pp
from html.parser import HTMLParser
from pathlib import Path
import textwrap
from enum import Enum
import difflib

NOW = datetime.now().isoformat(timespec='seconds', sep=',')
DRYRUN = False
CHOPPER_NAME = '.chopper.html'


class c:
    MAGENTA = '\033[95m'
    RED = '\033[31m'
    REDB = '\033[41m'
    BLUE = '\033[34m'
    BBLUE = '\033[94m'
    BLUEB = '\033[44m'
    BCYAN = '\033[96m'
    CYAN = '\033[36m'
    CYANB = '\033[46m'
    GREEN = '\033[32m'
    BGREEN = '\033[92m'
    GREENB = '\033[42m'
    BLACK = '\033[30m'
    BBLACK = '\033[90m'
    BLACKb = '\033[40m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'


class Action(Enum):
    CHOP = 'Chop'
    WRITE = 'Write'
    NEW = 'New'
    DIR = 'Mkdir'
    UNCHANGED = 'File unchanged'


def info(action, filename, dry_run=False, last=False):
    dry_run = ' (DRY RUN)' if dry_run else ''
    choppa = f'{c.MAGENTA}{c.BOLD}CHOPPER:{c.RESET}'
    task = f'{c.BGREEN}{action.value}{dry_run}{c.RESET}'
    filename = f'{c.BBLUE}{filename}{c.RESET}'
    tree = ''
    if action != action.CHOP:
        tree = '└─ ' if last else '├─ '
    date = ''
    if action == action.CHOP:
        date = f'{c.BBLACK}{NOW}{c.RESET}'
    print(f'{choppa} {tree}{task} {filename}  {date}')


def error(action, filename, msg, dry_run=False):
    dry_run = ' (DRY RUN)' if dry_run else ''
    choppa = f'{c.REDB}{c.BOLD}CHOPPER:{c.RESET}'
    action = f'{c.REDB}{c.BOLD}{action.value}{dry_run}{c.RESET}'
    filename = f'{c.BBLUE}{filename}{c.RESET}'
    print(choppa, action, msg, filename, file=sys.stderr)


class HTMLParser(HTMLParser):
    tags = ['style', 'script', 'chop']
    tree = []
    path = None
    parsed_data = []
    start = None

    def handle_starttag(self, tag, attrs):
        if tag in self.tags:
            self.tree.append(tag)
            for attr in attrs:
                if attr[0] == 'chopper:file':
                    self.path = attr[1]
                    self.start = self.getpos()

    def handle_endtag(self, tag):
        if tag in self.tags:
            start_tag = self.tree.pop()
            if not self.tree:
                self.parsed_data.append({
                    'path': self.path,
                    'tag': tag,
                    'start': self.start,
                    'end': self.getpos(),
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
            if filename.endswith(CHOPPER_NAME):
                chopper_files.append(os.path.join(root, filename))

    return chopper_files


def chop(source, types, comments, warn=False):
    info(Action.CHOP, source)
    with open(source, 'r') as f:
        source_html = f.read()

    parser = HTMLParser()
    parser.parsed_data.clear()
    parser.feed(source_html)
    data = parser.parsed_data

    source_html = source_html.splitlines()
    block_count = len(data) - 1
    for i, block in enumerate(data):
        block['base_path'] = types[block['tag']]
        block['path'] = magic_vars(block['path'], source)
        start = block['start'][0]
        end = block['end'][0] - 1
        raw_content = source_html[start:end]
        content = '\n'.join(raw_content)
        content = textwrap.dedent(content)
        block['content'] = content
        if comments:
            c = comments[block['tag']]
            if not raw_content:
                block['content'] = f'{c[0]}Chopper: No content{c[1]}'
            text = [source, block['path']]
            dest = Path(os.path.join(block['base_path'], block['path']))
            comment = f'{c[0]}{source} - {dest}{c[1]}'
            block['content'] = f'\n{comment}\n\n{block["content"]}'

        last = False if block_count != i else True
        make_file(block, warn, last)


def magic_vars(path, source):
    source = Path(source)
    source_name = source.name.replace(CHOPPER_NAME, '')
    new_name = path.format(NAME=source_name)
    return new_name


def make_file(block, warn=False, last=False):
    content = f'{block["content"]}'
    partial = Path(os.path.join(block['base_path'], block['path']))
    if not DRYRUN:
        if partial.parent.mkdir(parents=True, exist_ok=True):
            info(Action.DIR, partial.parent)

        if partial.exists():
            with open(partial, 'r+') as f:
                write_to_file(block, content, f, last, partial, warn, False)
        else:
            with open(partial, 'w') as f:
                write_to_file(block, content, f, last, partial, False, True)

    else:
        info(Action.WRITE, partial, dry_run=True, last=last)


def write_to_file(block, content, f, last, partial, warn, newfile):
    try:
        current_contents = f.read()
    except io.UnsupportedOperation:
        pass
    # print('>>>', current_contents)
    # current_contents = f'{current_contents.rstrip()}'
    # show_diff(content, current_contents, block['path'], str(partial))
    # print(len(current_contents), len(content))
    if current_contents != content:
        if warn:
            error(Action.WRITE, partial, 'File contents differ')
            show_diff(content, current_contents, block['path'], str(partial))
            print()
            sys.exit(1)
        else:
            if newfile:
                info(Action.NEW, partial, last=last)
            else:
                info(Action.WRITE, partial, last=last)
            f.seek(0)
            f.write(content)
            f.truncate()
    else:
        info(Action.UNCHANGED, partial, last=last)


def show_diff(a, b, fname_a, fname_b):
    diff = difflib.context_diff(
        a.splitlines(),
        b.splitlines(),
        tofile=fname_a,
        fromfile=fname_b,
        n=3
    )
    print()
    for l in diff:
        l = l.rstrip()
        if l.startswith('*'):
            color = c.RED
        elif l.startswith('-'):
            color = c.GREEN

        if l.startswith('!'):
            print(f'{color}{l}{c.RESET}')
        elif l.startswith('--'):
            print(f'{c.BLACK}{c.REDB}{l}{c.RESET}')
        elif l.startswith('****'):
            hl = '=' * 80
            print()
            print(f'{c.BCYAN}{hl}{c.RESET}')
            print()
        elif l.startswith('*'):
            print(f'{c.BLACK}{c.GREENB}{l}{c.RESET}')
        else:
            print(l)


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
        nargs='?',
        default=None,
        const='STANDARD_COMMENTS',
        help='Add comments to generated files. Seperate start and end comments with a comma')
    parser.add_argument(
        '--warn',
        action='store_true',
        help='Warn when the file contents differs instead of overwriting it.'
    )
    parser.add_argument(
        '--dry-run',
        action="store_true",
        help="Do not write any file to the filesystem")
    parser.add_argument(
        'source_dir',
        metavar='SOURCE-DIR',
        help='The directory that contains the chopper files.')

    args = parser.parse_args()

    global DRYRUN
    DRYRUN = args.dry_run

    if os.path.isdir(args.source_dir):
        chopper_files = find_chopper_files(args.source_dir)
    else:
        chopper_files = [args.source_dir]
    types = {
        'script': args.script_dir or '',
        'style': args.style_dir or '',
        'chop': args.html_dir or '',
    }

    comments = None
    if args.comments == 'STANDARD_COMMENTS':
        comment_types = {
            'script': ['// ', ''],
            'style': ['/* ', ' */'],
            'chop': ['<!-- ', ' -->'],
        }
    elif args.comments:
        comments = args.comments.split(',')
        comment_types = {
            'script': comments,
            'style': comments,
            'chop': comments,
        }
    else:
        comment_types = None

    for source in chopper_files:
        chop(source, types, comment_types, warn=args.warn)
    print()

if __name__ == '__main__':
    main()

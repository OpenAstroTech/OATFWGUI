#!/bin/env python3
import re
import sys
import argparse

import git
import semver

parser = argparse.ArgumentParser(usage='Set package version, checking to make sure the latest git tag matches')
parser.add_argument('-f', '--file', default='_version.py',
                    help='Version file to modify (default %(default)s')
parser.add_argument('PRE',
                    help='Semver pre-release')


def get_latest_tag():
    tags = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)
    if len(tags) == 0:
        return None
    return tags[-1]


def main():
    try:
        with open(args.file, 'r') as fp:
            old_file_contents = fp.read()
    except FileNotFoundError as e:
        print(f'Could not read file: {args.file}')
        sys.exit(1)

    version_var_re = re.compile(r'__version__\s*=\s*\'(.+?)\'')
    version_match = version_var_re.search(old_file_contents)
    if not version_match:
        print(f'Regex failed on contents: {old_file_contents}')
        sys.exit(1)
    old_version_str = version_match.group(1)
    print(f'Current version string: {old_version_str}')

    latest_tag = get_latest_tag()
    print(f'Latest tag is {latest_tag}')
    if str(latest_tag) != old_version_str:
        print('Latest tag does not match version!')
        sys.exit(1)

    head_sha = str(repo.head.object.hexsha)
    print(f'HEAD sha is {head_sha}')
    head_short_sha = head_sha[:6]

    new_version_str = f'{old_version_str}-{args.PRE}+{head_short_sha}'
    if not semver.VersionInfo.isvalid(new_version_str):
        print(f'{new_version_str} is not a valid version!')
        sys.exit(1)

    print(f'Writing new version string: {new_version_str}')
    new_file_contents = old_file_contents.replace(old_version_str, new_version_str)
    with open(args.file, 'w') as fp:
        fp.write(new_file_contents)


if __name__ == '__main__':
    repo = git.Repo('.', search_parent_directories=True)
    args = parser.parse_args()
    main()

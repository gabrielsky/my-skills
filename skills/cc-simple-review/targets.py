#!/usr/bin/env python3
"""Print cc-simple-review targets as JSON.

usage: targets.py [--uncommitted] [commit ...]
  --uncommitted  include uncommitted + untracked changes
  commit         commits picked by cc-code-scope (merge commits are skipped)

Changed lines come from `git blame` on the current files, so line numbers match
what the IDE sees even when the picked commits are scattered or later edited.
"""
import json
import os
import re
import subprocess
import sys

EXTS = ('.java', '.kt')
UNCOMMITTED = '0' * 40
BLAME_HEADER = re.compile(r'^([0-9a-f]{40}) \d+ (\d+)')
NOISE_LINE = re.compile(r'^(import |package |//|/\*|\*|[{}();\s]*$)')


def git(*args):
    return subprocess.run(['git', *args], capture_output=True, text=True, check=True).stdout


def parse_diff(diff, origin, touched, deleted):
    path = old = None
    for line in diff.splitlines():
        if line.startswith('--- '):
            old = line[6:] if line.startswith('--- a/') else None
        elif line.startswith('+++ '):
            path = line[6:] if line.startswith('+++ b/') else old
            if line.startswith('+++ b/'):
                touched.add(path)
        elif line.startswith('-') and path and path.endswith(EXTS):
            text = line[1:].strip()
            if not NOISE_LINE.match(text):
                entry = {'c': origin, 't': text}
                if entry not in deleted.setdefault(path, []):
                    deleted[path].append(entry)


def to_ranges(nums):
    ranges = []
    for n in sorted(nums):
        if ranges and n == ranges[-1][1] + 1:
            ranges[-1][1] = n
        else:
            ranges.append([n, n])
    return ranges


def main():
    args = sys.argv[1:]
    uncommitted = '--uncommitted' in args
    refs = [a for a in args if a != '--uncommitted']
    if not refs and not uncommitted:
        sys.exit('usage: targets.py [--uncommitted] [commit ...]')
    os.chdir(git('rev-parse', '--show-toplevel').strip())

    commits, skipped = [], []
    for ref in refs:
        try:
            sha, parents, subject = git('log', '-1', '--format=%H%x00%P%x00%s', ref).strip().split('\0')
        except subprocess.CalledProcessError:
            sys.exit(f'无法解析 commit: {ref}')
        (skipped if ' ' in parents else commits).append((sha, subject))

    owners = {h for h, _ in commits}
    touched, deleted, untracked = set(), {}, set()
    for h, _ in commits:
        parse_diff(git('show', '-U0', '--format=', '--no-color', h), h[:7], touched, deleted)
    if uncommitted:
        owners.add(UNCOMMITTED)
        parse_diff(git('diff', 'HEAD', '-U0', '--no-color'), 'uncommitted', touched, deleted)
        untracked = set(git('ls-files', '--others', '--exclude-standard').splitlines())
        touched |= untracked

    files = {}
    for path in sorted(touched):
        if not path.endswith(EXTS) or not os.path.isfile(path):
            continue
        if path in untracked:
            with open(path, encoding='utf-8', errors='replace') as f:
                lines = range(1, sum(1 for _ in f) + 1)
        else:
            lines = [int(m.group(2)) for m in map(BLAME_HEADER.match,
                     git('blame', '--line-porcelain', '--', path).splitlines())
                     if m and m.group(1) in owners]
        if lines:
            files[path] = to_ranges(lines)

    json.dump({
        'projectPath': os.getcwd(),
        'commits': [f'{h[:7]} {s}' for h, s in commits]
                   + [f'{h[:7]} {s}（merge，跳过）' for h, s in skipped]
                   + (['uncommitted'] if uncommitted else []),
        'files': files,
        'deleted': deleted,
    }, sys.stdout, ensure_ascii=False)


if __name__ == '__main__':
    main()

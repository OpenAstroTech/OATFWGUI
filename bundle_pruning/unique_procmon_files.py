#!/usr/bin/env python3
import argparse
import csv
import os
import pathlib
from typing import List

parser = argparse.ArgumentParser(usage='')
parser.add_argument('csv_file',
                    help='')
parser.add_argument('original_dir',
                    help='')


def get_needed_files() -> List[pathlib.PurePosixPath]:
    unique_path_names = set()
    with open(args.csv_file, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            access_path = row['Path']
            if 'HKCU' not in access_path:
                access_path_posix = pathlib.PurePosixPath(pathlib.PureWindowsPath(access_path).as_posix())
                unique_path_names.add(access_path_posix)

    common_prefix = os.path.commonpath([u for u in unique_path_names])
    prefix_removed_path_names = []
    for unique_path_name in unique_path_names:
        relative_path = unique_path_name.relative_to(common_prefix)
        if relative_path != pathlib.Path('.'):
            prefix_removed_path_names.append(relative_path)
    return sorted(prefix_removed_path_names, key=lambda x: len(str(x)))


def get_all_files(all_files_dir: pathlib.Path) -> List[pathlib.Path]:
    paths_in_original = list(all_files_dir.glob('**/*'))
    return paths_in_original


def get_path_size(p: pathlib.Path):
    if p.is_file():
        return p.stat().st_size
    elif p.is_dir():
        return sum(f.stat().st_size for f in p.glob('**/*') if f.is_file())
    else:
        raise IOError(f'wat {p}')


def byte_size_to_mb_str(byte_size: int) -> str:
    return f'{byte_size / (1024 * 1024):.2f}M'


def main():
    needed_files_rel = get_needed_files()
    all_files_dir = pathlib.Path(args.original_dir).resolve()
    all_files = get_all_files(all_files_dir)

    needed_paths = [pathlib.Path(all_files_dir, n) for n in needed_files_rel]
    print(f'Keep paths: {[str(f.relative_to(all_files_dir)) for f in needed_paths]}', end='\n\n')

    # Prune pure directories
    needed_files = [n for n in needed_paths if n.is_file()]
    needed_dirs = set(n.parent for n in needed_files)
    print(f'Keep dirs: {[str(r.relative_to(all_files_dir)) for r in needed_dirs]}', end='\n\n')

    all_files_sorted = sorted([p for p in all_files], key=lambda x: len(x.parts))

    all_pure_dirs = set(f for f in all_files_sorted if f.is_dir())
    all_parent_dirs = set(f.parent for f in all_files_sorted
                          if f.parent.relative_to(all_files_dir) != pathlib.Path('.'))
    all_dirs_sorted = sorted(all_pure_dirs | all_parent_dirs, key=lambda x: len(x.parts))
    print(f'All dirs: {[str(d) for d in all_dirs_sorted]}', end='\n\n')

    deletable_dirs = set()
    for original_dir in all_dirs_sorted:
        higher_dir_already_deletable = any(original_dir.is_relative_to(d) for d in deletable_dirs)
        if higher_dir_already_deletable:
            continue
        original_dir_lower_than_a_needed_dir = any(d.is_relative_to(original_dir) for d in needed_dirs)
        if not original_dir_lower_than_a_needed_dir:
            deletable_dirs.add(original_dir)
    print(f'Deletable dirs:{[str(d.relative_to(all_files_dir)) for d in deletable_dirs]}')

    # Prune files not needed, and not already handled by the directory deletion
    deletable_files = set()
    for original_file in [f for f in all_files_sorted if f.is_file()]:
        file_needed = any(original_file == f for f in needed_files)
        if file_needed:
            continue
        dir_already_pruned = any(original_file.is_relative_to(d) for d in deletable_dirs)
        if dir_already_pruned:
            continue
        deletable_files.add(original_file)
    print(f'Deletable files:{[str(f.relative_to(all_files_dir)) for f in deletable_files]}')

    for deletable_dir in sorted(deletable_dirs, key=get_path_size, reverse=True):
        mb_size_str = byte_size_to_mb_str(get_path_size(deletable_dir))
        print(f'{mb_size_str}\t{str(deletable_dir.relative_to(all_files_dir))}')
    for deletable_file in sorted(deletable_files, key=get_path_size, reverse=True):
        mb_size_str = byte_size_to_mb_str(get_path_size(deletable_file))
        print(f'{mb_size_str}\t{str(deletable_file.relative_to(all_files_dir))}')
    total_removed_bytes = sum(get_path_size(p) for p in (deletable_dirs | deletable_files))
    print(f'Total size removable: {byte_size_to_mb_str(total_removed_bytes)}')


if __name__ == '__main__':
    args = parser.parse_args()
    main()

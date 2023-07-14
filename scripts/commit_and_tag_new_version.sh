#!/bin/bash
set -e

version_file='./OATFWGUI/_version.py'
new_version=$(python3 -c "
exec(open('${version_file}').read())
print(__version__, end=None)
")
echo "New version from $version_file is $new_version"
git commit -am "Version $new_version"
git tag "$new_version"
git push
git push origin "$new_version"

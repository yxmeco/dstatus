#!/bin/bash

WORK_DIR="$(cd "$(dirname $0)" && pwd)"
cd $WORK_DIR || exit 1

commit="YW-$(date +%Y%m%d): auto add commit"
# shellcheck disable=SC1072
if [ -n "$1" ];then
 commit=$1
fi

git add --all && git commit -m "$commit" && git push
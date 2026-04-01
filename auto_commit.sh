#!/bin/bash
cd /home/asmile/wip/ripristino-test/Moving-One-Billion-People-/
if [ -n "$(git status --porcelain)" ]; then
    git add -A
    git commit -m "auto: save progress $(date '+%Y-%m-%d %H:%M')"
    git push
fi

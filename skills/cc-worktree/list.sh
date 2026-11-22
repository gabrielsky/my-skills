#!/usr/bin/env bash
# 列出当前仓库除主 worktree 外的所有 worktree，每行 TSV：
#   path  branch  dirty(未提交文件数)  active(最近活跃)  current(1=会话所在)  commits(领先主干的提交，最多 3 条)  files(未提交文件，最多 5 个)
# 主干 = 主 worktree 当前所在分支。
# 排序：有未提交改动的优先，再按最近活跃倒序。最近活跃 = max(最后提交时间, 未提交文件的 mtime)
set -euo pipefail

cur=$(git rev-parse --show-toplevel)
now=$(date +%s)
wts=$(git worktree list --porcelain | sed -n 's/^worktree //p')
base=$(git -C "$(head -1 <<<"$wts")" branch --show-current)

ago() {
  local s=$((now - $1))
  if   ((s < 3600));  then echo "$((s / 60))分钟前"
  elif ((s < 86400)); then echo "$((s / 3600))小时前"
  else                     echo "$((s / 86400))天前"
  fi
}

while IFS= read -r wt; do
  git -C "$wt" rev-parse --is-inside-work-tree >/dev/null 2>&1 || continue # 已删除 / bare
  branch=$(git -C "$wt" branch --show-current)
  [ -n "$branch" ] || branch="(detached $(git -C "$wt" rev-parse --short HEAD))"
  files=$({ git -C "$wt" diff --name-only HEAD; git -C "$wt" ls-files --others --exclude-standard; } | sort -u)
  dirty=$(grep -c . <<<"$files" || true)
  active=$(git -C "$wt" log -1 --format=%ct)
  while IFS= read -r f; do
    [ -e "$wt/$f" ] || continue
    m=$(stat -f %m "$wt/$f") # ponytail: macOS stat 语法，Linux 上改 stat -c %Y
    ((m > active)) && active=$m
  done <<<"$files"
  commits=$(git -C "$wt" log --format=%s "$base..HEAD" | head -3 | paste -sd'|' -)
  printf '%d\t%d\t%s\t%s\t%d\t%s\t%d\t%s\t%s\n' \
    "$((dirty > 0))" "$active" "$wt" "$branch" "$dirty" "$(ago "$active")" \
    "$([ "$wt" = "$cur" ] && echo 1 || echo 0)" "$commits" "$(head -5 <<<"$files" | paste -sd, -)"
done < <(tail -n +2 <<<"$wts") | sort -t$'\t' -k1,1nr -k2,2nr | cut -f3-

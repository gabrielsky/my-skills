#!/usr/bin/env bash
# 以实体为入口量搬家代价。
# 用法：[DOMAIN=<域>] [FILES=1] [DAYS=30] bash analyze-entity.sh <Entity> [<Entity>...]
#   siblings 段（不给 DOMAIN 时输出）：疑似与入参同领域的其他实体 + 依据（启发式，要人裁决）
#   spillover 段：每个入参实体的领域内 / 领域外引用面与 verdict
#   DOMAIN 不给时取引用入参实体最多的 core/module/<域>；FILES=1 列出领域外引用文件（W=疑似写该实体）
# 只读；用 git grep（只扫已跟踪文件，天然排除 .worktrees/ 与 target/）。
set -euo pipefail
[ $# -gt 0 ] || { sed -n '2,6p' "$0"; exit 1; }
DAYS="${DAYS:-30}"
cd "$(git rev-parse --show-toplevel)"
EDIR=metis-entity/src/main/java/com/darcytech/metis/entity
ALL="$(git grep -lE '^@(Entity|MappedSuperclass)' -- "$EDIR" | sort)"

file_of() { grep -E "/$1\.java$" <<<"$ALL" | head -1; }
fqn_of()  { sed -E 's#^metis-entity/src/main/java/##; s#\.java$##; s#/#.#g' <<<"$1"; }
# 去掉注释行：javadoc 里的 {@link 别的实体} 不算结构关联
code_of() { grep -vE '^[[:space:]]*(\*|//|/\*)' "$1"; }
# 一次 git grep 建「文件<TAB>实体FQN」索引，后面全走内存（实体之间同包互引不走 import，由「结构」信号覆盖）
IDX="$(git grep -hHoE 'import com\.darcytech\.metis\.entity\.[A-Za-z0-9_.]+;?' -- '*.java' '*.kt' \
       | grep -v "^$EDIR/" | grep -v '/src/test/' | sed -E 's#:import #\t#; s#;$##' || true)"
users_of() { awk -F'\t' -v q="$1" '$2==q{print $1}' <<<"$IDX" | sort -u; }
domains_of() { sed -nE 's#.*/core/module/([^/]+)/.*#\1#p' | sort -u; }

SEEDS=()
for s in "$@"; do f="$(file_of "$s")"; [ -n "$f" ] || { echo "找不到实体: $s" >&2; exit 1; }; SEEDS+=("$s"); done

if [ -z "${DOMAIN:-}" ]; then
  echo "# siblings（不含入参；依据越多越可能同域。BASE=公共基类，COMMON=被 >=3 个 core 领域引用，二者通常不属于本域）"
  for f in $ALL; do
    x="$(basename "$f" .java)"; why=""
    for s in "${SEEDS[@]}"; do [ "$s" = "$x" ] && continue 2; done
    xu="$(users_of "$(fqn_of "$f")")"
    for s in "${SEEDS[@]}"; do
      sf="$(file_of "$s")"
      if code_of "$sf" | grep -qE "\\b$x\\b" || code_of "$f" | grep -qE "\\b$s\\b"; then why+="结构($s) "; fi
      sd="$(dirname "$sf")"
      if [ "$sd" = "$(dirname "$f")" ] && [ "$(basename "$sd")" != node ]; then why+="同子包 "; fi
      case "$x" in "$s"*) why+="前缀($s) ";; esac
      case "$s" in "$x"*) why+="前缀($s) ";; esac
      co="$(comm -12 <(users_of "$(fqn_of "$sf")") <(sort -u <<<"$xu") | grep -vc '/mysql/node/dao/' || true)"
      [ "$co" -ge 2 ] && why+="共用文件($s):$co "
    done
    [ -n "$why" ] || continue
    if grep -q '^@MappedSuperclass' "$f"; then why+="BASE "; fi
    nd="$(domains_of <<<"$xu" | grep -c . || true)"
    if [ "$nd" -ge 3 ]; then why+="COMMON(域:$nd) "; fi
    printf '  %-60s %s\n' "${f#$EDIR/}" "$why"
  done
  DOMAIN="$(for s in "${SEEDS[@]}"; do users_of "$(fqn_of "$(file_of "$s")")"; done \
            | sed -nE 's#.*/core/module/([^/]+)/.*#\1#p' | sort | uniq -c | sort -rn | awk 'NR==1{print $2}')"
fi

echo "# spillover   domain=${DOMAIN:-<无：core/module 下没有引用方，需新建域>}"
for s in "${SEEDS[@]}"; do
  sf="$(file_of "$s")"; users="$(users_of "$(fqn_of "$sf")")"
  camel="$(tr '[:upper:]' '[:lower:]' <<<"${s:0:1}")${s:1}"
  # 写 = new / builder，或经 <实体名>Dao / <实体名>TxService 这类同名 bean 调写方法；只认对象名，避免把"写了别的实体"算进来
  wpat="new $s\\(|$s\\.builder\\(\\)|\\b${camel}[A-Za-z]*\\.(save|saveAll|forceUpdate|delete|update)[A-Za-z]*\\("
  # 必须锚 /core/module/：metis-web 有同名镜像包 web/module/<域>/，只写 /module/<域>/ 会把它误算成领域内
  in="$(grep -c "/core/module/${DOMAIN:-__none__}/" <<<"$users" || true)"
  out="$(grep -v "/core/module/${DOMAIN:-__none__}/" <<<"$users" | grep -v '/mysql/node/dao/' | grep . || true)"
  outn="$(grep -c . <<<"$out" || true)"
  writers=""
  if [ -n "$out" ]; then writers="$(xargs grep -lE "$wpat" <<<"$out" || true)"; fi
  bymod="$(sed -E 's#^(metis-pda/[^/]+|[^/]+)/.*#\1#' <<<"$out" | grep . | sort | uniq -c | awk '{printf "%s:%s ", $2, $1}' || true)"
  otherdoms="$(domains_of <<<"$out" | tr '\n' ' ')"
  touched="$(git log --all --since="${DAYS} days ago" --oneline -- "$sf" | wc -l | tr -d ' ')"
  # 启发式初筛：BLOCK:backend-web 可信；web-write 与 NARROW 都要人打开 W 文件确认
  if grep -q '^metis-backend-web/' <<<"$out"; then verdict="BLOCK:backend-web"
  elif grep -q '^metis-web/' <<<"$writers"; then verdict="BLOCK:web-write"
  elif [ "$outn" -gt 0 ]; then verdict="NARROW"
  else verdict="GO"; fi
  printf '  %-40s %-18s in=%-3s out=%-3s W=%-3s entityCommits(%sd)=%s  %s%s\n' "$s" "$verdict" "$in" "$outn" \
    "$(grep -c . <<<"$writers" || true)" "$DAYS" "$touched" "$bymod" "${otherdoms:+ otherDomains: $otherdoms}"
  if [ -n "${FILES:-}" ] && [ "$outn" -gt 0 ]; then
    while IFS= read -r o; do
      if grep -qxF "$o" <<<"$writers"; then m=W; else m=' '; fi
      echo "      $m $o"
    done <<<"$out"
  fi
done
API="metis-core/src/main/java/com/darcytech/metis/core/module/${DOMAIN:-__none__}/api"
if [ -d "$API" ]; then
  echo "# 域现有 api（读方改走 api 时先看缺什么）"
  git grep -hE '^ +[A-Za-z<][^=;(]* [a-zA-Z]+\(' -- "$API" | sed -E 's/^ +/  /' || true
fi

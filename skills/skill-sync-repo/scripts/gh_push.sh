#!/bin/bash
# 非交互推送 GitHub 仓库（凭据不落 .git/config、不进命令行参数）。
#
# 用法：
#   gh_push.sh <repo-dir> [remote] [branch]
#   gh_push.sh ~/WorkBuddy/2026-07-30-09-39-41/agent-employees
#
# 依赖：~/.workbuddy/secrets/gh_token.txt（600，由 gh_token_probe.py 生成或手工写入）
#
# 为什么需要它：
#   macOS 默认 credential.helper=osxkeychain，取密需 GUI 授权 → 非交互必报
#   "could not read Username for 'https://github.com'"。GIT_ASKPASS 绕开 keychain。
#   本机出网经代理，github.com:443 会间歇 502 → 内置重试 + ls-remote 校验。
set -uo pipefail

REPO_DIR="${1:?用法: gh_push.sh <repo-dir> [remote] [branch]}"
REMOTE="${2:-origin}"
BRANCH="${3:-main}"
TOKEN_FILE="${GH_TOKEN_FILE:-$HOME/.workbuddy/secrets/gh_token.txt}"
ASKPASS="${TMPDIR:-/tmp}/gh_askpass.sh"

[ -f "$TOKEN_FILE" ] || { echo "🔴 缺少 token 文件：$TOKEN_FILE"; echo "   先生成：python3 $(dirname "$0")/gh_token_probe.py"; exit 2; }
cd "$REPO_DIR" || exit 2

# 1) 构造 askpass（只读密钥文件，token 不出现于任何命令行/配置）
cat > "$ASKPASS" <<'EOF'
#!/bin/sh
case "$1" in
  *Username*) echo "x-access-token" ;;
  *) cat "${GH_TOKEN_FILE:-$HOME/.workbuddy/secrets/gh_token.txt}" ;;
esac
EOF
chmod 700 "$ASKPASS"
export GH_TOKEN_FILE="$TOKEN_FILE"

# 2) 沙箱残留锁（.git 内文件在沙箱下不可 unlink）
rm -f .git/index.lock 2>/dev/null

echo "仓：$(pwd)"
echo "远端：$(git remote get-url "$REMOTE" 2>/dev/null || echo '未配置')"
echo "待推提交："; git log --oneline "$REMOTE/$BRANCH..HEAD" 2>/dev/null | head -10

# 3) 重试推送（代理抖动）
#    ⚠️ 必须设 low-speed 阈值：代理有时不是「快速 502」而是「挂死不返回」，
#    没有阈值时 git 会无限期等待（实测挂 >5 分钟）。这里 20 秒低于 1KB/s 即判失败并重试。
#    ⚠️ 必须 `-c credential.helper=` 关掉 osxkeychain：否则 git 收尾时会尝试把凭据写进
#    login.keychain，沙箱里该写入被拒 → 命令整体退出码非 0 → **脚本误报失败**（实际已推成功）。
export GIT_HTTP_LOW_SPEED_LIMIT=1000
export GIT_HTTP_LOW_SPEED_TIME=20
GIT_NO_HELPER=(-c credential.helper=)
ok=0
for i in 1 2 3 4 5 6; do
  out=$(GIT_ASKPASS="$ASKPASS" GIT_TERMINAL_PROMPT=0 git "${GIT_NO_HELPER[@]}" push "$REMOTE" "$BRANCH" 2>&1)
  rc=$?
  echo "--- try $i (rc=$rc) ---"; echo "$out" | tail -3
  if [ $rc -eq 0 ]; then ok=1; break; fi
  sleep 4
done

# 4) 校验远端 HEAD == 本地 HEAD
[ $ok -eq 1 ] || { echo "🔴 push 失败（6 次）。若是恒定 502，见 SKILL.md 注意事项 10 的降级通道。"; exit 1; }
local_sha=$(git rev-parse HEAD)
# ⚠️ 私有仓的 ls-remote 也需要认证（公开仓匿名可读）→ 必须同样带 GIT_ASKPASS，
#    否则私有仓会返回空，误报「远端 sha 与本地不一致」。
remote_sha=$(GIT_ASKPASS="$ASKPASS" GIT_TERMINAL_PROMPT=0 git "${GIT_NO_HELPER[@]}" ls-remote "$REMOTE" -h "refs/heads/$BRANCH" 2>/dev/null | awk '{print $1}')
echo "本地 HEAD：$local_sha"
echo "远端 HEAD：${remote_sha:-<取不到>}"
if [ "$local_sha" = "$remote_sha" ]; then echo "✅ 已同步"; else echo "⚠️ 远端 sha 与本地不一致（私有仓取不到时先查 GIT_ASKPASS 是否生效），请复查"; exit 1; fi

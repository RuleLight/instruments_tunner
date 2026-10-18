#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "正在推送至 https://github.com/RuleLight/instruments_tunner.git ..."
git remote set-url origin "https://github.com/RuleLight/instruments_tunner.git" 2>/dev/null || git remote add origin "https://github.com/RuleLight/instruments_tunner.git"
git push -u origin main
echo "✅ 已成功开源并推送至 https://github.com/RuleLight/instruments_tunner"

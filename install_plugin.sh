#!/bin/bash
# oh-my-Dynamic Codex Plugin 安装脚本
# 用法: bash install_plugin.sh

set -e

PLUGIN_DIR="$HOME/Desktop/oh-my-Dynamic/codex-plugin"
SKILLS_DIR="$HOME/.agents/skills"

echo "🚀 安装 oh-my-Dynamic Codex 插件..."
echo ""

# 1. 创建 skills 目录
mkdir -p "$SKILLS_DIR"

# 2. 符号链接 skills
echo "📦 安装 Skills..."

# oh-my-dynamic skill
ln -sf "$PLUGIN_DIR/skills/oh-my-dynamic" "$SKILLS_DIR/oh-my-dynamic"
echo "  ✅ oh-my-dynamic"

# multi-agent-run skill
ln -sf "$PLUGIN_DIR/skills/multi-agent-run" "$SKILLS_DIR/multi-agent-run"
echo "  ✅ multi-agent-run"

# 3. 安装 marketplace（个人级）
MARKETPLACE_DIR="$HOME/.agents/plugins"
mkdir -p "$MARKETPLACE_DIR"

# 更新 marketplace.json
if [ -f "$MARKETPLACE_DIR/marketplace.json" ]; then
    echo "📋 marketplace.json 已存在，跳过（手动合并即可）"
else
    cp "$HOME/Desktop/oh-my-Dynamic/.agents/plugins/marketplace.json" "$MARKETPLACE_DIR/marketplace.json"
    echo "  ✅ marketplace.json 已安装"
fi

# 4. 验证
echo ""
echo "──────────────────────────────────"
echo "验证安装:"
echo ""

if [ -d "$SKILLS_DIR/oh-my-dynamic" ]; then
    echo "  ✅ oh-my-dynamic skill"
else
    echo "  ❌ oh-my-dynamic skill 失败"
fi

if [ -d "$SKILLS_DIR/multi-agent-run" ]; then
    echo "  ✅ multi-agent-run skill"
else
    echo "  ❌ multi-agent-run skill 失败"
fi

echo ""
echo "🎉 安装完成!"
echo ""
echo "使用方式:"
echo "  Codex CLI: $oh-my-dynamic <query>"
echo "  Codex CLI: $multi-agent-run <query>"
echo "  或让 Codex 自动匹配复杂任务"
echo ""
echo "重启 Codex 使插件生效。"

#!/bin/bash
# oh-my-Dynamic Codex Plugin 安装脚本
# 用法: bash install_plugin.sh

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$PROJECT_DIR/codex-plugin"
SKILLS_DIR="$HOME/.agents/skills"

echo "🚀 安装 oh-my-Dynamic Codex 插件..."
echo ""

# 1. 创建 skills 目录
mkdir -p "$SKILLS_DIR"

# 2. 符号链接 skills
echo "📦 安装 Skills..."

link_skill() {
    local source_dir="$1"
    local target_dir="$2"
    local label="$3"

    if [ ! -d "$source_dir" ]; then
        echo "  ❌ $label 源目录不存在: $source_dir"
        exit 1
    fi

    if [ -e "$target_dir" ] && [ ! -L "$target_dir" ]; then
        echo "  ❌ $label 目标已存在且不是符号链接: $target_dir"
        echo "     请先手动备份/删除，避免覆盖已有 skill。"
        exit 1
    fi

    ln -sfn "$source_dir" "$target_dir"
    echo "  ✅ $label"
}

# oh-my-dynamic skill
link_skill "$PLUGIN_DIR/skills/oh-my-dynamic" "$SKILLS_DIR/oh-my-dynamic" "oh-my-dynamic"

# multi-agent-run skill
link_skill "$PLUGIN_DIR/skills/multi-agent-run" "$SKILLS_DIR/multi-agent-run" "multi-agent-run"

# 3. 安装 marketplace（个人级）
MARKETPLACE_DIR="$HOME/.agents/plugins"
mkdir -p "$MARKETPLACE_DIR"
MARKETPLACE_PLUGIN_DIR="$MARKETPLACE_DIR/plugins/oh-my-dynamic"
mkdir -p "$MARKETPLACE_DIR/plugins"

if [ -e "$MARKETPLACE_PLUGIN_DIR" ] && [ ! -L "$MARKETPLACE_PLUGIN_DIR" ]; then
    echo "📋 marketplace plugin 目录已存在，跳过链接: $MARKETPLACE_PLUGIN_DIR"
else
    ln -sfn "$PLUGIN_DIR" "$MARKETPLACE_PLUGIN_DIR"
    echo "  ✅ marketplace plugin link"
fi

# 更新 marketplace.json
if [ -f "$MARKETPLACE_DIR/marketplace.json" ]; then
    echo "📋 marketplace.json 已存在，跳过（手动合并即可）"
else
    cp "$PROJECT_DIR/.agents/plugins/marketplace.json" "$MARKETPLACE_DIR/marketplace.json"
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
echo '  Codex App: $oh-my-dynamic <query>'
echo '  Codex App: $multi-agent-run <query>'
echo "  或让 Codex 自动匹配复杂任务"
echo ""
echo "重启 Codex App 或新开 thread 使插件生效。默认使用 App 内部 LLM，无需 API Key。"

#!/bin/bash
# oh-my-Dynamic Codex Plugin 安装脚本
# 用法: bash install_plugin.sh [--uninstall]

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$PROJECT_DIR/codex-plugin"
SKILLS_DIR="$HOME/.agents/skills"

echo "🚀 安装 oh-my-Dynamic Codex 插件..."
echo ""

MARKETPLACE_DIR="$HOME/.agents/plugins"
MARKETPLACE_JSON="$MARKETPLACE_DIR/marketplace.json"

if [ "${1:-}" = "--uninstall" ]; then
    echo "🧹 卸载 oh-my-Dynamic Codex 插件..."
    echo ""

    remove_link() {
        local target_dir="$1"
        local expected_source="$2"
        local label="$3"

        if [ ! -e "$target_dir" ] && [ ! -L "$target_dir" ]; then
            echo "  ✅ $label 未安装"
            return
        fi
        if [ ! -L "$target_dir" ]; then
            echo "  ⚠️  $label 不是符号链接，跳过: $target_dir"
            return
        fi
        local current_target
        current_target="$(readlink "$target_dir")"
        if [ "$current_target" != "$expected_source" ]; then
            echo "  ⚠️  $label 指向其他位置，跳过: $target_dir -> $current_target"
            return
        fi
        rm "$target_dir"
        echo "  ✅ 已移除 $label"
    }

    remove_link "$SKILLS_DIR/oh-my-dynamic" "$PLUGIN_DIR/skills/oh-my-dynamic" "oh-my-dynamic skill"
    remove_link "$SKILLS_DIR/multi-agent-run" "$PLUGIN_DIR/skills/multi-agent-run" "multi-agent-run skill"
    remove_link "$MARKETPLACE_DIR/plugins/oh-my-dynamic" "$PLUGIN_DIR" "marketplace plugin link"

    if [ -f "$MARKETPLACE_JSON" ]; then
        python - "$MARKETPLACE_JSON" <<'PY'
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

marketplace_path = Path(sys.argv[1])
try:
    data = json.loads(marketplace_path.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    raise SystemExit(f"marketplace.json JSON 无效，请先手动修复: {exc}") from exc

plugins = data.get("plugins", [])
updated_plugins = [plugin for plugin in plugins if plugin.get("name") != "oh-my-dynamic"]
if len(updated_plugins) == len(plugins):
    print("  ✅ marketplace.json 未包含 oh-my-dynamic")
    raise SystemExit(0)

backup_path = marketplace_path.with_name(
    f"{marketplace_path.name}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
)
shutil.copy2(marketplace_path, backup_path)
data["plugins"] = updated_plugins
marketplace_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"  ✅ 已移除 marketplace 条目，并备份: {backup_path}")
PY
    else
        echo "  ✅ marketplace.json 不存在"
    fi

    echo ""
    echo "卸载完成。raw traces 如需清理，可删除项目内 .orchestry/。"
    exit 0
fi

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
mkdir -p "$MARKETPLACE_DIR"
MARKETPLACE_PLUGIN_DIR="$MARKETPLACE_DIR/plugins/oh-my-dynamic"
mkdir -p "$MARKETPLACE_DIR/plugins"

if [ -e "$MARKETPLACE_PLUGIN_DIR" ] && [ ! -L "$MARKETPLACE_PLUGIN_DIR" ]; then
    echo "📋 marketplace plugin 目录已存在，跳过链接: $MARKETPLACE_PLUGIN_DIR"
else
    ln -sfn "$PLUGIN_DIR" "$MARKETPLACE_PLUGIN_DIR"
    echo "  ✅ marketplace plugin link"
fi

# 更新 marketplace.json：保留其他插件，合并/更新 oh-my-dynamic 条目
MARKETPLACE_TEMPLATE="$PROJECT_DIR/.agents/plugins/marketplace.json"

echo "📋 更新 marketplace.json..."
python - "$MARKETPLACE_JSON" "$MARKETPLACE_TEMPLATE" "$PLUGIN_DIR" <<'PY'
import copy
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

marketplace_path = Path(sys.argv[1])
template_path = Path(sys.argv[2])
plugin_dir = str(Path(sys.argv[3]).resolve())
relative_plugin_path = "./plugins/oh-my-dynamic"
plugin_name = "oh-my-dynamic"

if not template_path.exists():
    raise SystemExit(f"marketplace template 不存在: {template_path}")

try:
    with template_path.open("r", encoding="utf-8") as f:
        template = json.load(f)
except json.JSONDecodeError as exc:
    raise SystemExit(f"marketplace template JSON 无效: {exc}") from exc

template_plugins = template.get("plugins", [])
template_entry = next(
    (plugin for plugin in template_plugins if plugin.get("name") == plugin_name),
    {
        "name": plugin_name,
        "policy": {"installation": "AVAILABLE", "authentication": "ON_USE"},
        "category": "Developer Tools",
    },
)

if marketplace_path.exists():
    try:
        with marketplace_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"现有 marketplace.json JSON 无效，请先修复: {marketplace_path}: {exc}") from exc
else:
    data = {
        "name": template.get("name", "oh-my-dynamic-plugins"),
        "interface": template.get(
            "interface",
            {"displayName": "oh-my-Dynamic Multi-Agent Orchestration"},
        ),
        "plugins": [],
    }

plugins = data.setdefault("plugins", [])
existing_index = next(
    (index for index, plugin in enumerate(plugins) if plugin.get("name") == plugin_name),
    None,
)

entry = copy.deepcopy(template_entry)
if existing_index is not None:
    merged = copy.deepcopy(plugins[existing_index])
    merged.update(entry)
    entry = merged

entry["name"] = plugin_name
entry["source"] = {
    "source": "local",
    "path": relative_plugin_path,
}

updated = copy.deepcopy(data)
updated_plugins = list(updated.get("plugins", []))
if existing_index is None:
    updated_plugins.append(entry)
else:
    updated_plugins[existing_index] = entry
updated["plugins"] = updated_plugins

if marketplace_path.exists() and data == updated:
    print("  ✅ marketplace.json 已是最新")
    raise SystemExit(0)

marketplace_path.parent.mkdir(parents=True, exist_ok=True)
if marketplace_path.exists():
    backup_path = marketplace_path.with_name(
        f"{marketplace_path.name}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )
    shutil.copy2(marketplace_path, backup_path)
    print(f"  ✅ 已备份原 marketplace.json: {backup_path}")

with marketplace_path.open("w", encoding="utf-8") as f:
    json.dump(updated, f, ensure_ascii=False, indent=2)
    f.write("\n")

print("  ✅ marketplace.json 已合并 oh-my-dynamic")
PY

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

if python -m json.tool "$MARKETPLACE_JSON" >/dev/null; then
    echo "  ✅ marketplace.json JSON"
else
    echo "  ❌ marketplace.json JSON 失败"
fi

echo ""
echo "🎉 安装完成!"
echo ""
echo "使用方式:"
echo '  Codex App: $oh-my-dynamic <query>'
echo '  Codex App: $multi-agent-run <query>'
echo "  或让 Codex 自动匹配复杂任务"
echo ""
echo "验证路径:"
echo "  $SKILLS_DIR/oh-my-dynamic"
echo "  $SKILLS_DIR/multi-agent-run"
echo "  $MARKETPLACE_JSON"
echo ""
echo "重启 Codex App 或新开 thread 使插件生效。默认使用 App 内部 LLM，无需 API Key。"

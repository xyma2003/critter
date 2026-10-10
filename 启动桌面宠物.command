#!/bin/bash
set -u

fail() {
    printf '\n%s\n' "$1" >&2
    if [[ -t 0 ]]; then
        read -r -p "按回车关闭此窗口……" || true
    fi
    exit "${2:-1}"
}

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)" \
    || fail "无法定位 Critter 项目目录。"
cd -- "$project_dir" || fail "无法进入 Critter 项目目录。"

python_bin="$project_dir/.venv/bin/python"
if [[ ! -x "$python_bin" ]]; then
    printf '请在终端进入项目目录：\n  cd %q\n' "$project_dir" >&2
    printf '然后使用 Python 3.10 或更高版本完成首次安装：\n' >&2
    printf '  python3 -m venv .venv\n  .venv/bin/python -m pip install -r requirements.txt\n' >&2
    fail "未找到可运行的 .venv/bin/python；完成安装后再双击启动。"
fi

if [[ ! -f "$project_dir/main.py" ]]; then
    fail "找不到 main.py，请将启动脚本放回 Critter 项目根目录。"
fi

# Check availability without importing the app, reading credentials, or calling a model.
"$python_bin" - <<'PY'
import importlib.util
import sys

if sys.version_info < (3, 10):
    print("Critter 需要 Python 3.10 或更高版本，请使用新版本重建 .venv。", file=sys.stderr)
    sys.exit(1)

packages = {
    "PyQt6": "PyQt6", "requests": "requests", "bs4": "beautifulsoup4",
    "PIL": "Pillow", "lxml": "lxml", "langgraph": "langgraph",
    "langchain_openai": "langchain-openai", "langchain_anthropic": "langchain-anthropic",
    "langchain_core": "langchain-core", "anthropic": "anthropic", "dotenv": "python-dotenv",
}
missing = [package for module, package in packages.items() if importlib.util.find_spec(module) is None]
if missing:
    print("缺少依赖：" + ", ".join(missing), file=sys.stderr)
    sys.exit(1)
PY
if [[ $? -ne 0 ]]; then
    fail "运行环境未就绪。在项目目录执行 .venv/bin/python -m pip install -r requirements.txt 后重试。"
fi

printf '正在启动 Critter：%s\n' "$project_dir"
"$python_bin" "$project_dir/main.py"
app_status=$?
if [[ "$app_status" -ne 0 ]]; then
    fail "Critter 异常退出（退出码 ${app_status}），请查看上方错误信息。" "$app_status"
fi

#!/usr/bin/env python3
"""
DeerFlow 完整打包脚本
打包 Gateway API（含嵌入式 LangGraph 运行时）+ Next.js 前端 (standalone 模式)

架构说明：
===========
打包后的 DeerFlowGateway 是一个单一可执行文件，包含：
1. Gateway API (端口 8001) - REST API 服务
2. 嵌入式 LangGraph 运行时 - 通过 DeerFlowClient 实现，无需独立 LangGraph Server
3. 前端静态文件服务（可选，设置 DEERFLOW_STATIC_DIR 环境变量）

关键技术：
- PyInstaller: 打包 Python 代码为单文件可执行文件
- DeerFlowClient: 嵌入式客户端，在进程内运行 Agent
- Next.js standalone: 独立运行的前端，需要 Node.js

打包结构：
deer-flow-package/
├── DeerFlowGateway        # Gateway API + 嵌入式 LangGraph (PyInstaller 单文件)
├── frontend/              # Next.js standalone 前端
│   ├── server.js          # 入口文件
│   ├── .next/static/      # 静态资源
│   ├── node_modules/      # (需运行 install.sh 安装)
│   └── public/            # 公共资源
├── config.yaml            # 主配置文件
├── config.example.yaml    # 配置模板
├── extensions_config.json # MCP/Skills 配置
├── .env.example           # 环境变量模板
├── install.sh             # 安装依赖脚本
├── start.sh               # 完整启动脚本（前端 + Gateway）
├── stop.sh                # 停止脚本
└── start-dev.sh           # 开发模式启动（仅 Gateway）

使用方法：
1. 运行打包: python3 package.py
2. 部署: 复制 dist/deer-flow-package/ 到目标机器
3. 安装依赖: ./install.sh
4. 配置: 编辑 .env 设置 API 密钥
5. 启动: ./start.sh

依赖要求：
- pnpm: 前端构建
- Python 虚拟环境: 后端打包 (deer-flow/backend/.venv)
- PyInstaller: 已安装在虚拟环境中
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEERFLOW_ROOT = PROJECT_ROOT / "deer-flow"
BACKEND_DIR = DEERFLOW_ROOT / "backend"
FRONTEND_DIR = DEERFLOW_ROOT / "frontend"
OUTPUT_DIR = PROJECT_ROOT / "dist" / "deer-flow-package"

# 颜色定义
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
NC = "\033[0m"


def log(msg: str, level: str = "info"):
    """打印日志"""
    colors = {"info": GREEN, "warn": YELLOW, "error": RED, "step": BLUE}
    color = colors.get(level, "")
    print(f"{color}[打包] {msg}{NC}")


def run_command(cmd: list, cwd: Path, env: dict = None) -> bool:
    """运行命令"""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    result = subprocess.run(cmd, cwd=cwd, env=full_env)
    return result.returncode == 0


def check_dependencies():
    """检查依赖"""
    log("=" * 50)
    log("检查依赖...")
    log("=" * 50)

    # 检查 pnpm
    result = subprocess.run(["which", "pnpm"], capture_output=True)
    if result.returncode != 0:
        log("错误: 未找到 pnpm，请先安装: npm install -g pnpm", "error")
        return False
    log("✓ pnpm 已安装")

    # 检查 Python 虚拟环境
    venv_python = BACKEND_DIR / ".venv" / "bin" / "python"
    if not venv_python.exists():
        log(f"错误: 虚拟环境不存在: {venv_python}", "error")
        log("请先运行: cd deer-flow/backend && uv venv && uv pip install -e .", "warn")
        return False
    log("✓ Python 虚拟环境已存在")

    # 检查 PyInstaller
    result = subprocess.run(
        [str(venv_python), "-c", "import PyInstaller"],
        capture_output=True
    )
    if result.returncode != 0:
        log("错误: PyInstaller 未安装", "error")
        log("请先运行: cd deer-flow/backend && uv pip install pyinstaller", "warn")
        return False
    log("✓ PyInstaller 已安装")

    return True


def build_gateway():
    """构建 Gateway API（PyInstaller）"""
    log("=" * 50)
    log("构建 Gateway API...")
    log("=" * 50)

    spec_file = BACKEND_DIR / "DeerFlowGateway.spec"
    venv_python = BACKEND_DIR / ".venv" / "bin" / "python"

    if not spec_file.exists():
        log(f"错误: spec 文件不存在: {spec_file}", "error")
        return False

    # 运行 PyInstaller
    cmd = [
        str(venv_python),
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_file),
    ]

    log("执行: pyinstaller --clean --noconfirm DeerFlowGateway.spec")
    if not run_command(cmd, BACKEND_DIR):
        log("Gateway 构建失败", "error")
        return False

    # 检查输出
    exe_path = BACKEND_DIR / "dist" / "DeerFlowGateway"
    if not exe_path.exists():
        log(f"错误: 可执行文件不存在: {exe_path}", "error")
        return False

    log(f"✓ Gateway 构建完成: {exe_path}")
    return True


def build_frontend():
    """构建 Next.js 前端（standalone 模式）"""
    log("=" * 50)
    log("构建 Next.js 前端 (standalone)...")
    log("=" * 50)

    # 检查 node_modules
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        log("安装前端依赖...")
        if not run_command(["pnpm", "install"], FRONTEND_DIR):
            log("前端依赖安装失败", "error")
            return False

    # 构建（standalone 模式）
    log("构建 frontend (这可能需要几分钟)...")
    env = {
        "SKIP_ENV_VALIDATION": "1",
        "NODE_ENV": "production",
    }
    if not run_command(["pnpm", "build"], FRONTEND_DIR, env):
        log("前端构建失败", "error")
        return False

    # 检查输出
    standalone_dir = FRONTEND_DIR / ".next" / "standalone"
    if not standalone_dir.exists():
        log(f"错误: standalone 输出不存在: {standalone_dir}", "error")
        return False

    log(f"✓ 前端构建完成: {standalone_dir}")
    return True


# 前端不需要复制的文件/目录（standalone 模式只需要 server.js + .next + public）
FRONTEND_EXCLUDE_PATTERNS = [
    # 源码目录
    "src",
    # 开发配置文件（保留 .env.example, package.json, pnpm-lock.yaml）
    "*.md",
    "Dockerfile",
    "eslint.config.js",
    "tsconfig.json",
    "next.config.ts",
    "postcss.config.js",
    "prettier.config.js",
    "pnpm-workspace.yaml",
    "Makefile",
    "components.json",
    # 脚本和辅助文件
    "scripts",
    "start.js",
    "start-frontend.js",
    "package-lock.json",
]


def _should_exclude_frontend(name: str, in_node_modules: bool = False) -> bool:
    """检查前端文件是否应该排除

    Args:
        name: 文件/目录名
        in_node_modules: 是否在 node_modules 目录内部（内部不排除 src 等）
    """
    import fnmatch
    # 在 node_modules 内部不排除任何目录（保留依赖完整性）
    if in_node_modules:
        return False
    for pattern in FRONTEND_EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def _copy_tree_filtered(src: Path, dest: Path, in_node_modules: bool = False) -> int:
    """复制目录树，排除不需要的文件

    Args:
        src: 源目录
        dest: 目标目录
        in_node_modules: 是否在 node_modules 目录内部
    """
    import fnmatch
    count = 0
    dest.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        # 检查是否在 node_modules 内部
        is_in_node_modules = in_node_modules or item.name == "node_modules"

        if _should_exclude_frontend(item.name, in_node_modules):
            continue

        if item.is_dir():
            count += _copy_tree_filtered(item, dest / item.name, is_in_node_modules)
        else:
            shutil.copy2(item, dest / item.name)
            count += 1

    return count


def _create_runtime_package_json() -> dict:
    """创建运行时 package.json，包含原始所有依赖"""
    import json

    # 直接复制原始 package.json 的依赖
    src_package = FRONTEND_DIR / "package.json"
    with open(src_package) as f:
        original = json.load(f)

    # 创建运行时 package.json（保留所有 dependencies）
    return {
        "name": "deer-flow-frontend-runtime",
        "version": "1.0.0",
        "private": True,
        "type": "module",
        "scripts": {
            "start": "node server.js"
        },
        "pnpm": {
            "onlyBuiltDependencies": ["esbuild", "sharp"]
        },
        "dependencies": dict(original.get("dependencies", {}))
    }


def package_all():
    """打包所有组件"""
    log("=" * 50)
    log("打包所有组件...")
    log("=" * 50)

    # 清理输出目录
    if OUTPUT_DIR.exists():
        log(f"清理输出目录: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    # 1. 复制 Gateway
    gateway_exe = BACKEND_DIR / "dist" / "DeerFlowGateway"
    if gateway_exe.exists():
        shutil.copy2(gateway_exe, OUTPUT_DIR / "DeerFlowGateway")
        log(f"✓ 复制 DeerFlowGateway ({gateway_exe.stat().st_size / 1024 / 1024:.1f}MB)")
    else:
        log("错误: 找不到 DeerFlowGateway", "error")
        return False

    # 2. 复制前端（standalone，包含完整 node_modules）
    frontend_src = FRONTEND_DIR / ".next" / "standalone"
    frontend_dest = OUTPUT_DIR / "frontend"

    log("复制前端文件（含 node_modules）...")

    # 复制整个 standalone 目录
    frontend_dest.mkdir(parents=True, exist_ok=True)

    # 复制 server.js
    server_js = frontend_src / "server.js"
    if server_js.exists():
        shutil.copy2(server_js, frontend_dest / "server.js")

    # 复制 .next 目录
    next_src = frontend_src / ".next"
    next_dest = frontend_dest / ".next"
    if next_src.exists():
        file_count = _copy_tree_filtered(next_src, next_dest)
        log(f"✓ 复制 .next ({file_count} 个文件)")

    # 不复制 node_modules，而是创建运行时 package.json，通过 install.sh 安装
    # 这样可以大大减小打包体积，用户运行 install.sh 即可安装依赖

    # 复制静态资源
    static_src = FRONTEND_DIR / ".next" / "static"
    static_dest = frontend_dest / ".next" / "static"
    if static_src.exists():
        if static_dest.exists():
            shutil.rmtree(static_dest)
        shutil.copytree(static_src, static_dest)
        log("✓ 复制 .next/static")

    # 复制 public 目录
    public_src = FRONTEND_DIR / "public"
    public_dest = frontend_dest / "public"
    if public_src.exists():
        if public_dest.exists():
            shutil.rmtree(public_dest)
        shutil.copytree(public_src, public_dest)
        log("✓ 复制 public")

    # 创建运行时 package.json（包含原始所有依赖）
    log("创建运行时 package.json...")
    import json
    runtime_pkg = _create_runtime_package_json()
    with open(frontend_dest / "package.json", "w") as f:
        json.dump(runtime_pkg, f, indent=2)
    log(f"✓ 创建 package.json ({len(runtime_pkg.get('dependencies', {}))} 个依赖)")

    # 复制 pnpm-lock.yaml 以锁定依赖版本
    lockfile_src = FRONTEND_DIR / "pnpm-lock.yaml"
    if lockfile_src.exists():
        shutil.copy2(lockfile_src, frontend_dest / "pnpm-lock.yaml")
        log("✓ 复制 pnpm-lock.yaml（锁定依赖版本）")

    log("✓ 前端复制完成（需运行 install.sh 安装依赖）")

    # 3. 复制 Node.js 运行时（如果存在）
    node_src = DEERFLOW_ROOT / "node"
    if node_src.exists():
        node_dest = OUTPUT_DIR / "node"
        if node_dest.exists():
            shutil.rmtree(node_dest)

        # 复制完整 Node.js 目录（bin + lib）
        node_dest.mkdir(parents=True)

        # 复制 bin 目录
        if (node_src / "bin").exists():
            shutil.copytree(node_src / "bin", node_dest / "bin")
            # 确保可执行权限
            for f in (node_dest / "bin").glob("*"):
                f.chmod(0o755)

        # 复制 lib 目录（包含 npm, corepack）
        if (node_src / "lib").exists():
            shutil.copytree(node_src / "lib", node_dest / "lib")

        # 计算总大小
        total_size = sum(f.stat().st_size for f in node_dest.rglob("*") if f.is_file())
        log(f"✓ 复制 Node.js 运行时 ({total_size / 1024 / 1024:.1f}MB)")
    else:
        log("⚠ 跳过 Node.js (deer-flow/node 不存在，用户需自行安装)")

    # 4. 复制配置文件
    config_files = [
        "config.yaml",
        "config.example.yaml",
        "extensions_config.json",
        ".env.example",
    ]

    for cfg in config_files:
        src = DEERFLOW_ROOT / cfg
        if src.exists():
            shutil.copy2(src, OUTPUT_DIR / cfg)
            log(f"✓ 复制 {cfg}")
        else:
            log(f"⚠ 跳过 {cfg} (不存在)")

    # 4. 复制技能目录
    skills_src = DEERFLOW_ROOT / "skills"
    skills_dest = OUTPUT_DIR / "skills"
    if skills_src.exists():
        if skills_dest.exists():
            shutil.rmtree(skills_dest)
        shutil.copytree(skills_src, skills_dest)
        skill_count = len(list(skills_dest.glob("**/*"))) - 1  # 减去目录本身
        log(f"✓ 复制 skills ({skill_count} 个文件)")
    else:
        log("⚠ 跳过 skills (不存在)")

    return True


def create_scripts():
    """创建启动/停止脚本"""
    log("=" * 50)
    log("创建启动脚本...")
    log("=" * 50)

    # 安装依赖脚本
    install_script = '''#!/bin/bash
# DeerFlow 依赖安装脚本
# 安装前端所需的 node_modules

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
RED='\\033[0;31m'
BLUE='\\033[0;34m'
NC='\\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

log_info "=========================================="
log_info "DeerFlow 依赖安装"
log_info "=========================================="

# 设置 Node.js 命令：优先使用打包目录中的 node，其次使用系统 node
BUNDLED_NODE="$SCRIPT_DIR/node/bin/node"
BUNDLED_NPM="$SCRIPT_DIR/node/bin/npm"
if [ -x "$BUNDLED_NODE" ]; then
    export PATH="$SCRIPT_DIR/node/bin:$PATH"
    NODE_CMD="$BUNDLED_NODE"
    NPM_CMD="$BUNDLED_NPM"
    log_info "✓ 使用打包目录中的 Node.js: $($NODE_CMD -v)"
elif command -v node &> /dev/null; then
    NODE_CMD="node"
    NPM_CMD="npm"
    log_info "✓ 使用系统 Node.js: $($NODE_CMD -v)"
else
    log_error "未找到 Node.js"
    log_info "请安装 Node.js 20+ 或确保 node/bin/node 二进制存在"
    exit 1
fi

NODE_VERSION=$($NODE_CMD -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 20 ]; then
    log_error "Node.js 版本过低 (当前: v$($NODE_CMD -v))，需要 20+"
    exit 1
fi

# 检查 pnpm
if ! command -v pnpm &> /dev/null; then
    log_warn "未找到 pnpm，正在安装..."
    $NPM_CMD install -g pnpm
    if [ $? -ne 0 ]; then
        log_error "pnpm 安装失败"
        exit 1
    fi
fi
log_info "✓ pnpm 版本: $(pnpm -v)"

# 安装前端依赖
FRONTEND_DIR="$SCRIPT_DIR/frontend"
if [ -d "$FRONTEND_DIR" ]; then
    log_step "安装前端依赖..."
    cd "$FRONTEND_DIR"

    if [ -f "package.json" ]; then
        # 使用 pnpm 安装，只安装 production 依赖
        # 原生模块（esbuild, sharp）构建权限已在 package.json 的 pnpm.onlyBuiltDependencies 中配置
        pnpm install --prod

        if [ $? -ne 0 ]; then
            log_error "前端依赖安装失败"
            exit 1
        fi

        log_info "✓ 前端依赖安装完成"
    else
        log_error "未找到 frontend/package.json"
        exit 1
    fi
else
    log_error "未找到 frontend 目录"
    exit 1
fi

log_info ""
log_info "=========================================="
log_info "依赖安装完成!"
log_info "=========================================="
log_info "现在可以运行 ./start.sh 启动服务"
log_info ""
'''

    install_path = OUTPUT_DIR / "install.sh"
    install_path.write_text(install_script)
    install_path.chmod(0o755)
    log("✓ 创建 install.sh")

    # 启动脚本
    start_script = '''#!/bin/bash
# DeerFlow 完整启动脚本
# 自动杀死占用端口并启动服务

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
RED='\\033[0;31m'
BLUE='\\033[0;34m'
NC='\\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# 默认端口
GATEWAY_PORT=${GATEWAY_PORT:-8001}
FRONTEND_PORT=${FRONTEND_PORT:-3001}

# 设置 Node.js 命令：优先使用打包目录中的 node
BUNDLED_NODE="$SCRIPT_DIR/node/bin/node"
if [ -x "$BUNDLED_NODE" ]; then
    export PATH="$SCRIPT_DIR/node/bin:$PATH"
    NODE_CMD="$BUNDLED_NODE"
else
    NODE_CMD="node"
fi

# 强制杀死占用端口的进程
kill_port() {
    local port=$1
    log_step "检查端口 $port..."

    # 使用 fuser 强制杀死
    if fuser -k $port/tcp 2>/dev/null; then
        log_info "端口 $port 已释放"
        sleep 1
    fi

    # 备用方案：使用 lsof
    local pids=$(lsof -t -i:$port 2>/dev/null || true)
    if [ -n "$pids" ]; then
        log_warn "发现残留进程，强制终止..."
        for pid in $pids; do
            kill -9 $pid 2>/dev/null && log_info "已终止进程 $pid"
        done
        sleep 1
    fi
}

# 停止所有服务
stop_all() {
    log_info "停止所有服务..."

    # 杀死端口
    kill_port $GATEWAY_PORT
    kill_port $FRONTEND_PORT

    # 杀死相关进程
    pkill -9 -f "DeerFlowGateway" 2>/dev/null || true
    pkill -9 -f "next dev" 2>/dev/null || true

    log_info "所有服务已停止"
}

# 捕获退出信号（仅前台模式）
trap 'log_info "收到退出信号..."; stop_all; exit 0' INT TERM

# 检查前端依赖
FRONTEND_DIR="$SCRIPT_DIR/frontend"
if [ -d "$FRONTEND_DIR" ]; then
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        log_error "=========================================="
        log_error "前端依赖未安装!"
        log_error "=========================================="
        log_error "请先运行: ./install.sh"
        log_error ""
        exit 1
    fi
fi

# 设置配置路径
export DEER_FLOW_CONFIG_PATH="${DEER_FLOW_CONFIG_PATH:-$SCRIPT_DIR/config.yaml}"
export DEER_FLOW_EXTENSIONS_CONFIG_PATH="${DEER_FLOW_EXTENSIONS_CONFIG_PATH:-$SCRIPT_DIR/extensions_config.json}"
export DEER_FLOW_HOME="${DEER_FLOW_HOME:-$SCRIPT_DIR}"
export GATEWAY_PORT=$GATEWAY_PORT
export GATEWAY_HOST=0.0.0.0

log_info "=========================================="
log_info "DeerFlow 服务启动"
log_info "=========================================="
log_info "配置文件: $DEER_FLOW_CONFIG_PATH"
log_info "Gateway 端口: $GATEWAY_PORT"
log_info "前端端口: $FRONTEND_PORT"
log_info "=========================================="

# 检查并创建 .env 文件（不强制退出，仅提示）
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        log_info "创建 .env 文件..."
        cp .env.example .env
        log_warn "================================================"
        log_warn "请稍后编辑 .env 文件配置 API 密钥"
        log_warn "必需的密钥: ZHIPU_API_KEY"
        log_warn "================================================"
    fi
fi

# 加载 .env 文件
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# 停止旧服务
stop_all

# 启动 Gateway
log_step "启动 Gateway..."
./DeerFlowGateway > /tmp/gateway.log 2>&1 &
GATEWAY_PID=$!
log_info "Gateway PID: $GATEWAY_PID"

# 等待 Gateway 启动 (最多等待15秒)
log_step "等待 Gateway 启动..."
for i in {1..15}; do
    sleep 1
    if curl -s -o /dev/null -w "" http://localhost:$GATEWAY_PORT/health 2>/dev/null; then
        log_info "✓ Gateway 启动成功 (等待 ${i}秒)"
        break
    fi
    if [ $i -eq 15 ]; then
        log_error "✗ Gateway 启动超时"
        log_error "日志:"
        tail -20 /tmp/gateway.log
        exit 1
    fi
done

# 启动前端
log_step "启动前端..."
if [ -d "$FRONTEND_DIR" ]; then
    cd "$FRONTEND_DIR"
    BETTER_AUTH_SECRET="${BETTER_AUTH_SECRET:-deerflow-default-secret-key}" \
    BETTER_AUTH_URL="${BETTER_AUTH_URL:-http://localhost:$FRONTEND_PORT}" \
    PORT=$FRONTEND_PORT nohup $NODE_CMD server.js > /tmp/frontend.log 2>&1 &
    FRONTEND_PID=$!
    cd "$SCRIPT_DIR"
    log_info "前端 PID: $FRONTEND_PID"
    log_info "使用 Node: $NODE_CMD"

    # 等待前端启动
    for i in {1..15}; do
        sleep 1
        if curl -s -o /dev/null http://localhost:$FRONTEND_PORT 2>/dev/null; then
            log_info "✓ 前端启动成功 (等待 ${i}秒)"
            break
        fi
        if [ $i -eq 15 ]; then
            log_warn "前端启动超时，继续..."
        fi
    done
fi

log_info "=========================================="
log_info "所有服务已启动!"
log_info "=========================================="
log_info "前端:      http://localhost:$FRONTEND_PORT"
log_info "Gateway:   http://localhost:$GATEWAY_PORT"
log_info "API 文档:  http://localhost:$GATEWAY_PORT/docs"
log_info "=========================================="

# 保存 PID 到文件
echo "$GATEWAY_PID" > /tmp/deerflow_gateway.pid
[ -n "$FRONTEND_PID" ] && echo "$FRONTEND_PID" > /tmp/deerflow_frontend.pid

# 如果是前台模式，等待进程
if [ "$1" = "--foreground" ] || [ "$1" = "-f" ]; then
    log_info "前台模式运行，按 Ctrl+C 停止"
    log_info ""
    wait $GATEWAY_PID
else
    log_info "后台模式运行"
    log_info "停止服务: ./stop.sh 或 kill \\$(cat /tmp/deerflow_gateway.pid)"
    log_info ""
fi
'''

    script_path = OUTPUT_DIR / "start.sh"
    script_path.write_text(start_script)
    script_path.chmod(0o755)
    log(f"✓ 创建 start.sh")

    # 停止脚本
    stop_script = '''#!/bin/bash
# DeerFlow 强制停止脚本
# 强制停止所有相关服务和进程

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 颜色定义
GREEN='\\033[0;32m'
RED='\\033[0;31m'
NC='\\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

GATEWAY_PORT=${GATEWAY_PORT:-8001}
FRONTEND_PORT=${FRONTEND_PORT:-3001}

log_info "=========================================="
log_info "DeerFlow 强制停止"
log_info "=========================================="

# 方法1: 使用 fuser 强制杀死端口
log_info "释放端口 $GATEWAY_PORT..."
fuser -k -9 $GATEWAY_PORT/tcp 2>/dev/null && log_info "  ✓ 端口 $GATEWAY_PORT 已释放" || log_info "  - 端口 $GATEWAY_PORT 未被占用"

log_info "释放端口 $FRONTEND_PORT..."
fuser -k -9 $FRONTEND_PORT/tcp 2>/dev/null && log_info "  ✓ 端口 $FRONTEND_PORT 已释放" || log_info "  - 端口 $FRONTEND_PORT 未被占用"

# 方法2: 使用 pkill 强制杀死进程
log_info "终止相关进程..."
pkill -9 -f "DeerFlowGateway" 2>/dev/null && log_info "  ✓ DeerFlowGateway 已终止" || true
pkill -9 -f "next dev" 2>/dev/null && log_info "  ✓ Next.js 已终止" || true
pkill -9 -f "node.*server.js" 2>/dev/null && log_info "  ✓ Node.js 已终止" || true

# 方法3: 使用 PID 文件
if [ -f /tmp/deerflow_gateway.pid ]; then
    pid=$(cat /tmp/deerflow_gateway.pid)
    kill -9 $pid 2>/dev/null && log_info "  ✓ Gateway (PID: $pid) 已终止" || true
    rm -f /tmp/deerflow_gateway.pid
fi

if [ -f /tmp/deerflow_frontend.pid ]; then
    pid=$(cat /tmp/deerflow_frontend.pid)
    kill -9 $pid 2>/dev/null && log_info "  ✓ Frontend (PID: $pid) 已终止" || true
    rm -f /tmp/deerflow_frontend.pid
fi

# 方法4: 使用 lsof 备用
for port in $GATEWAY_PORT $FRONTEND_PORT; do
    pids=$(lsof -t -i:$port 2>/dev/null || true)
    if [ -n "$pids" ]; then
        for pid in $pids; do
            kill -9 $pid 2>/dev/null && log_info "  ✓ 进程 $pid (端口 $port) 已终止"
        done
    fi
done

# 清理日志文件
rm -f /tmp/gateway.log /tmp/frontend.log 2>/dev/null

log_info "=========================================="
log_info "所有服务已强制停止"
log_info "=========================================="
'''

    stop_path = OUTPUT_DIR / "stop.sh"
    stop_path.write_text(stop_script)
    stop_path.chmod(0o755)
    log(f"✓ 创建 stop.sh")

    # 开发模式启动脚本
    dev_script = '''#!/bin/bash
# DeerFlow 开发模式启动脚本
# 仅启动 Gateway，前端使用 deer-flow/frontend 的开发服务器

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 加载 .env
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# 设置配置路径
export DEER_FLOW_CONFIG_PATH="$SCRIPT_DIR/config.yaml"
export DEER_FLOW_EXTENSIONS_CONFIG_PATH="$SCRIPT_DIR/extensions_config.json"
export DEER_FLOW_HOME="$SCRIPT_DIR"

GATEWAY_PORT=${GATEWAY_PORT:-8001}

# 杀死占用端口
fuser -k $GATEWAY_PORT/tcp 2>/dev/null || true

echo "启动 Gateway API (开发模式)..."
echo "API 地址: http://localhost:$GATEWAY_PORT"
echo ""
echo "请在另一个终端启动前端开发服务器:"
echo "  cd deer-flow/frontend && pnpm dev"
echo ""

DEERFLOW_STATIC_DIR="" GATEWAY_PORT=$GATEWAY_PORT GATEWAY_HOST=0.0.0.0 ./DeerFlowGateway'''

    dev_path = OUTPUT_DIR / "start-dev.sh"
    dev_path.write_text(dev_script)
    dev_path.chmod(0o755)
    log(f"✓ 创建 start-dev.sh")


def calculate_size() -> str:
    """计算打包目录大小"""
    total = 0
    for item in OUTPUT_DIR.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return f"{total / 1024 / 1024:.1f}MB"


def main():
    log("=" * 60)
    log("DeerFlow 完整打包工具")
    log("Gateway API + Next.js 前端 (standalone)")
    log("=" * 60)
    print()

    # 1. 检查依赖
    if not check_dependencies():
        return 1

    print()

    # 2. 构建 Gateway
    if not build_gateway():
        log("Gateway 构建失败", "error")
        return 1

    print()

    # 3. 构建前端
    if not build_frontend():
        log("前端构建失败", "error")
        return 1

    print()

    # 4. 打包所有组件
    if not package_all():
        log("打包失败", "error")
        return 1

    # 5. 创建脚本
    create_scripts()

    # 统计
    print()
    log("=" * 60)
    log("打包完成!")
    log("=" * 60)
    print()
    log(f"输出目录: {OUTPUT_DIR}")
    log(f"总大小: {calculate_size()}")
    print()
    log("目录结构:")
    log("  ├── DeerFlowGateway    # Gateway API")
    log("  ├── frontend/          # Next.js 前端（需安装依赖）")
    log("  ├── config.yaml        # 配置文件")
    log("  ├── .env.example       # 环境变量模板")
    log("  ├── install.sh         # 安装依赖脚本")
    log("  ├── start.sh           # 启动脚本")
    log("  └── stop.sh            # 停止脚本")
    print()
    log("部署步骤:")
    log("  1. 复制 dist/deer-flow-package/ 到目标机器")
    log("  2. cd deer-flow-package")
    log("  3. ./install.sh        # 安装依赖（需要 Node.js 20+）")
    log("  4. cp .env.example .env && 编辑配置 API 密钥")
    log("  5. ./start.sh          # 启动服务")
    print()
    log("服务地址:")
    log("  前端:     http://localhost:3001")
    log("  API 文档: http://localhost:8001/docs")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())

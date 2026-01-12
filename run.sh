#!/bin/bash

# 获取脚本所在目录
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# 自动检测并激活虚拟环境
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "⚠️  未找到虚拟环境文件夹 (.venv 或 venv)"
    echo "正在尝试直接运行..."
fi

# 启动 Streamlit
streamlit run app.py
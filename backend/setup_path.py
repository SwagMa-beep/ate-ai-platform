"""
自动配置Python路径
在所有模块前导入此文件
"""
import sys
from pathlib import Path

# 获取backend目录的绝对路径
BACKEND_DIR = Path(__file__).resolve().parent

# 添加到sys.path（如果还没有）
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
    print(f"✅ 已添加到Python路径: {BACKEND_DIR}")
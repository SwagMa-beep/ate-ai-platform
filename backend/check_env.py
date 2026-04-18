"""
环境检查脚本
直接运行即可，不需要pytest
"""
import sys
from pathlib import Path


def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    print(f"Python版本: {version.major}.{version.minor}.{version.micro}")
    if version >= (3, 10):
        print("  ✅ 版本符合要求（>= 3.10）")
        return True
    else:
        print("  ❌ 版本过低，需要 >= 3.10")
        return False


def check_package(package_name, import_name=None, version_attr="__version__"):
    """检查包是否安装"""
    import_name = import_name or package_name
    try:
        module = __import__(import_name)
        version = getattr(module, version_attr, "未知")
        print(f"  ✅ {package_name:20s} 已安装 (版本: {version})")
        return True
    except ImportError:
        print(f"  ❌ {package_name:20s} 未安装 → pip install {package_name}")
        return False


def check_project_structure():
    """检查项目结构"""
    required_dirs = [
        "app",
        "app/core",
        "app/models",
        "app/services",
        "app/utils",
        "app/api",
        "app/api/v1",
        "tests",
        "../data",
        "../data/uploads",
        "../data/processed",
        "../logs"
    ]

    all_exist = True
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists():
            print(f"  ✅ {dir_path}")
        else:
            print(f"  ❌ {dir_path} 不存在")
            all_exist = False

    return all_exist


def check_sources_root():
    """检查是否正确配置Sources Root"""
    try:
        from app.core.config import get_settings
        print("  ✅ backend 已标记为 Sources Root")
        return True
    except ImportError as e:
        print("  ❌ backend 未标记为 Sources Root")
        print(f"     错误: {e}")
        print("     解决: 右键backend文件夹 → Mark Directory as → Sources Root")
        return False


def check_env_file():
    """检查.env文件"""
    env_file = Path(".env")
    if not env_file.exists():
        print("  ❌ .env 文件不存在")
        print("     请创建 backend/.env 文件")
        return False

    print("  ✅ .env 文件存在")

    # 检查API密钥
    try:
        with open(".env", "r", encoding="utf-8") as f:
            content = f.read()
            if "DEEPSEEK_API_KEY=sk-" in content and "sk-c3b84c6389494aae994e9626342c4aa8" in content:
                print("  ✅ DEEPSEEK_API_KEY 已配置")
                return True
            elif "DEEPSEEK_API_KEY=" in content:
                print("  ⚠️  DEEPSEEK_API_KEY 已设置（请确认密钥正确）")
                return True
            else:
                print("  ❌ DEEPSEEK_API_KEY 未配置")
                return False
    except Exception as e:
        print(f"  ❌ 读取.env失败: {e}")
        return False


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("ATE-AI-Platform 环境检查")
    print("=" * 70 + "\n")

    results = []

    # 1. Python版本
    print("1️⃣  Python版本检查")
    results.append(check_python_version())
    print()

    # 2. 必需的包
    print("2️⃣  依赖包检查")
    packages = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("pydantic", "pydantic"),
        ("pydantic-settings", "pydantic_settings"),
        ("openai", "openai"),
        ("instructor", "instructor"),
        ("loguru", "loguru"),
        ("pandas", "pandas"),
        ("openpyxl", "openpyxl"),
        ("pymupdf", "fitz"),
        ("pdfplumber", "pdfplumber"),
        ("tqdm", "tqdm"),
        ("python-dotenv", "dotenv"),
        ("requests", "requests"),
    ]

    for pkg_name, import_name in packages:
        results.append(check_package(pkg_name, import_name))
    print()

    # 3. 项目结构
    print("3️⃣  项目结构检查")
    results.append(check_project_structure())
    print()

    # 4. Sources Root配置
    print("4️⃣  PyCharm配置检查")
    results.append(check_sources_root())
    print()

    # 5. .env文件
    print("5️⃣  环境变量配置检查")
    results.append(check_env_file())
    print()

    # 总结
    print("=" * 70)
    total = len(results)
    passed = sum(results)

    if passed == total:
        print(f"🎉 恭喜！所有检查通过 ({passed}/{total})")
        print("=" * 70)
        print("\n✅ 环境配置完成，可以开始开发了！")
        print("\n下一步：")
        print("  1. 把PDF文件放到 data/raw/ 目录")
        print("  2. 运行: python cli.py --pdf ../data/raw/你的PDF.pdf")
        print("  或启动API: uvicorn app.main:app --reload")
    else:
        print(f"⚠️  部分检查未通过 ({passed}/{total})")
        print("=" * 70)
        print("\n请根据上面的 ❌ 提示修复问题")
        print("修复后重新运行: python check_env.py")

    print()


if __name__ == "__main__":
    main()
"""
命令行工具
用于直接运行提取（不需要启动API服务）
"""
import argparse
import sys
from pathlib import Path

# 添加项目路径到sys.path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.testplan_service import TestPlanService
from app.core.config import get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()


def main():
    """命令行主函数"""
    parser = argparse.ArgumentParser(
        description="ATE TestPlan自动提取工具（命令行版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 提取整个PDF
  python cli.py --pdf data/raw/LM317.pdf

  # 只提取第3-9页
  python cli.py --pdf data/raw/LM317.pdf --pages 3-9

  # 指定输出目录
  python cli.py --pdf data/raw/LM317.pdf --output output/

  # 设置并发数
  python cli.py --pdf data/raw/ADI-AD780.pdf --workers 3
        """
    )

    parser.add_argument(
        "--pdf",
        required=True,
        help="PDF文件路径"
    )

    parser.add_argument(
        "--pages",
        type=str,
        default=None,
        help="页码范围（如 3-9 或 3,4,5）"
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="并发数（1-10），默认5"
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出目录，默认为 data/processed/"
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="显示详细日志"
    )

    args = parser.parse_args()

    # 验证PDF文件
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        logger.error(f"❌ PDF文件不存在: {pdf_path}")
        sys.exit(1)

    # 验证并发数
    if not 1 <= args.workers <= 10:
        logger.error(f"❌ 并发数必须在1-10之间，当前: {args.workers}")
        sys.exit(1)

    # 显示配置
    print("\n" + "=" * 60)
    print("配置信息")
    print("=" * 60)
    print(f"PDF文件: {pdf_path.absolute()}")
    print(f"页码范围: {args.pages or '全部'}")
    print(f"并发数: {args.workers}")
    print(f"输出目录: {args.output or settings.PROCESSED_DIR}")
    print(f"API密钥: {'已配置' if settings.DEEPSEEK_API_KEY else '未配置'}")
    print("=" * 60 + "\n")

    # 检查API密钥
    if not settings.DEEPSEEK_API_KEY:
        logger.error("❌ DeepSeek API密钥未配置")
        logger.error("请在 backend/.env 文件中设置 DEEPSEEK_API_KEY")
        sys.exit(1)

    # 执行提取
    try:
        service = TestPlanService()
        result = service.extract_from_pdf(
            pdf_path=str(pdf_path),
            pages=args.pages,
            max_workers=args.workers
        )

        # 打印结果
        if result.status == "success":
            print("\n" + "=" * 60)
            print("✅ 提取成功！")
            print("=" * 60)
            print(f"芯片型号: {result.chip_name}")
            print(f"总参数数: {result.total_params}")
            print(f"  A类(电气特性): {result.a_params}")
            print(f"  B类(绝对最大值): {result.b_params}")
            print(f"  C类(工作条件): {result.c_params}")
            print(f"  已拦截: {result.blocked_params}")
            print("\n文件输出:")
            print(f"  📊 Excel: {result.excel_path}")
            print(f"  📄 JSON: {result.json_path}")
            print("=" * 60 + "\n")

            if result.warnings:
                print("⚠️  警告信息:")
                for warning in result.warnings[:5]:
                    print(f"  - {warning}")
                if len(result.warnings) > 5:
                    print(f"  ... 还有 {len(result.warnings) - 5} 条警告")

            sys.exit(0)
        else:
            print("\n" + "=" * 60)
            print("❌ 提取失败")
            print("=" * 60)
            for error in result.errors:
                print(f"  - {error}")
            print("=" * 60 + "\n")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("\n⚠️  用户中断操作")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 程序出错: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
"""
模块二命令行工具 - 支持自动读取引脚定义
"""
import argparse
import sys
import json
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.models.testplan import ExtractionResult, PinDefinition
from app.services.resource_mapping_service import ResourceMappingService
from app.utils.svg_generator import SVGGenerator
from app.utils.bom_generator import generate_bom_excel
from app.utils.resource_map_exporter import export_resource_map_excel
from app.core.config import get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger   = setup_logger()


def main():
    parser = argparse.ArgumentParser(
        description="ATE 资源映射工具（命令行版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 推荐：直接从模块一JSON读取（引脚自动提取）
  python cli2.py --json ../data/processed/Renesas-HD74LS00P_TestPlan.json

  # 手动指定芯片（引脚从--pins文件读取）
  python cli2.py --chip LM317 --type LDO --pins ../data/raw/LM317_pins.xlsx

  # 双工位LDO
  python cli2.py --json ../data/processed/LM317_TestPlan.json --dual

  # 生成PinMapping模板（当自动提取引脚失败时使用）
  python cli2.py --template DIGITAL_74
        """
    )

    parser.add_argument("--json",  type=str, default=None,
                        help="模块一JSON路径（推荐，自动读取引脚）")
    parser.add_argument("--chip",  type=str, default=None,
                        help="芯片型号（不用--json时填写）")
    parser.add_argument("--type",  type=str, default=None,
                        choices=[
                            "DIGITAL_74","DIGITAL_54","DIGITAL_4000",
                            "MEMORY","LDO","EEPROM","ANALOG_GENERAL","UNKNOWN"
                        ],
                        help="芯片类型（不用--json时填写）")
    parser.add_argument("--pins",  type=str, default=None,
                        help="PinMapping文件（JSON中无引脚时备用）")
    parser.add_argument("--dual",  action="store_true", default=False,
                        help="双工位适配器（LDO场景）")
    parser.add_argument("--output",type=str, default=None,
                        help="输出目录，默认data/processed/")
    parser.add_argument("--no-svg",action="store_true", default=False,
                        help="跳过SVG生成")
    parser.add_argument("--verbose","-v", action="store_true")
    parser.add_argument("--template", type=str, default=None,
                        metavar="CHIP_TYPE",
                        help="生成PinMapping模板，如 --template LDO")

    args = parser.parse_args()

    # ── 生成模板模式 ──────────────────────────────────────────
    if args.template:
        _generate_template(args.template)
        sys.exit(0)

    # ── 参数校验 ──────────────────────────────────────────────
    if not args.json and not (args.chip and args.type):
        logger.error("❌ 请提供 --json，或同时提供 --chip 和 --type")
        parser.print_help()
        sys.exit(1)

    # ── 打印标题 ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  模块二 - STS8200S 资源映射工具")
    print("=" * 60)

    # ── Step1: 读取芯片信息和引脚定义 ────────────────────────
    print("\n📂 Step 1: 读取芯片信息...")
    pin_df    = None
    all_pins  = []

    if args.json:
        json_path = Path(args.json)
        if not json_path.exists():
            logger.error(f"❌ JSON文件不存在: {json_path}")
            sys.exit(1)

        with open(json_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)

        chip_name = json_data.get("chip_name", "Unknown")
        chip_type = json_data.get("chip_type", "UNKNOWN")
        stats     = json_data.get("statistics", {})

        # ── 自动读取引脚定义 ──────────────────────────────
        pin_defs_raw = json_data.get("pin_definitions", [])

        if pin_defs_raw:
            # JSON中有引脚定义，直接使用
            pin_df = pd.DataFrame(pin_defs_raw)
            print(f"  ✅ 自动读取引脚: {len(pin_df)} 个 (来自模块一JSON)")

            if args.verbose:
                print("\n  引脚列表:")
                for p in pin_defs_raw:
                    print(
                        f"    Pin{p.get('pin_no','?'):>3} "
                        f"{str(p.get('pin_name','')):>8} "
                        f"[{p.get('direction','')}] "
                        f"{p.get('function','')}"
                    )
        else:
            # JSON中没有引脚定义
            print("  ⚠️  JSON中未找到引脚定义")

            if args.pins:
                # 用手动提供的文件
                pins_path = Path(args.pins)
                if not pins_path.exists():
                    logger.error(f"❌ PinMapping文件不存在: {pins_path}")
                    sys.exit(1)
                pin_df = (
                    pd.read_csv(pins_path)
                    if pins_path.suffix == ".csv"
                    else pd.read_excel(pins_path)
                )
                print(f"  ✅ 从文件读取引脚: {len(pin_df)} 个")
            else:
                # 提示重新运行模块一
                print("\n  ❗ 解决方案（任选一个）:")
                print("  方案1：重新运行模块一，会自动提取引脚")
                print(f"    python cli.py --pdf <PDF路径>")
                print("  方案2：生成模板手动填写")
                print(f"    python cli2.py --template {chip_type}")
                print(f"    python cli2.py --json {args.json} --pins ../data/raw/{chip_type}_PinMapping_Template.xlsx")
                sys.exit(1)

        extraction_result = ExtractionResult(
            status       = "success",
            chip_name    = chip_name,
            chip_type    = chip_type,
            total_params = stats.get("total",   0),
            a_params     = stats.get("A_class", 0),
            b_params     = stats.get("B_class", 0),
            c_params     = stats.get("C_class", 0),
        )
        print(f"  芯片型号: {chip_name}")
        print(f"  芯片类型: {chip_type}")

    else:
        # 手动模式
        chip_name = args.chip
        chip_type = args.type

        if not args.pins:
            logger.error("❌ 手动模式必须提供 --pins 文件")
            print(f"  提示: python cli2.py --template {chip_type}")
            sys.exit(1)

        pins_path = Path(args.pins)
        if not pins_path.exists():
            logger.error(f"❌ PinMapping文件不存在: {pins_path}")
            sys.exit(1)

        pin_df = (
            pd.read_csv(pins_path)
            if pins_path.suffix == ".csv"
            else pd.read_excel(pins_path)
        )

        extraction_result = ExtractionResult(
            status    = "success",
            chip_name = chip_name,
            chip_type = chip_type,
        )
        print(f"  ✅ 手动模式 | 芯片: {chip_name} [{chip_type}]")
        print(f"  ✅ 引脚文件: {pins_path} ({len(pin_df)}个引脚)")

    print(f"  双工位: {'是' if args.dual else '否'}")

    # ── Step2: 执行资源映射 ───────────────────────────────────
    print("\n🔌 Step 2: 执行资源映射...")

    try:
        service = ResourceMappingService()
        result  = service.generate_resource_map(
            extraction_result = extraction_result,
            pin_mapping_df    = pin_df,
            dual_site         = args.dual
        )

        if result.status != "success":
            print("\n❌ 资源映射失败!")
            for err in result.errors:
                print(f"  - {err}")
            sys.exit(1)

        print(f"  ✅ 适配器    : {result.adapter_model}")
        print(f"  ✅ 资源映射数: {len(result.resource_mappings)}")
        print(f"  ✅ PGS配置数 : {len(result.pgs_configs)}")

        if args.verbose:
            print("\n  资源映射详情:")
            for m in result.resource_mappings:
                print(
                    f"    Pin{m.pin_no:>3} {m.pin_name:>8} "
                    f"→ {m.sts_resource:>12} "
                    f"[{m.resource_type}]"
                )

    except Exception as e:
        logger.error(f"❌ 资源映射出错: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    # ── Step3: 导出文件 ───────────────────────────────────────
    print("\n💾 Step 3: 导出文件...")

    output_dir = (
        Path(args.output) if args.output else settings.PROCESSED_DIR
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 资源映射Excel
        excel_path = str(output_dir / f"{chip_name}_ResourceMap.xlsx")
        export_resource_map_excel(
            chip_name         = chip_name,
            chip_type         = chip_type,
            adapter_info      = result.adapter_info,
            resource_mappings = result.resource_mappings,
            pgs_configs       = result.pgs_configs,
            pgs_details       = result.pgs_detail_conditions,
            pin_groups        = result.pin_groups,
            output_path       = excel_path
        )
        print(f"  📊 资源映射Excel: {excel_path}")

        # SVG原理图
        if not args.no_svg:
            svg_path = str(output_dir / f"{chip_name}_Schematic.svg")
            SVGGenerator().generate(
                chip_name   = chip_name,
                chip_type   = chip_type,
                mappings    = result.resource_mappings,
                output_path = svg_path
            )
            print(f"  🖼️  SVG原理图   : {svg_path}")

        # BOM清单
        bom_path = str(output_dir / f"{chip_name}_BOM.xlsx")
        generate_bom_excel(
            bom_items     = result.adapter_info.bom_items,
            chip_name     = chip_name,
            adapter_model = result.adapter_model,
            output_path   = bom_path
        )
        print(f"  📋 BOM清单     : {bom_path}")

    except Exception as e:
        logger.error(f"❌ 文件导出失败: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    # ── 最终报告 ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  ✅ 模块二完成！- {chip_name} [{chip_type}]")
    print("=" * 60)
    print(f"  适配器   : {result.adapter_model}")
    print(f"  引脚映射 : {len(result.resource_mappings)} 个")
    print(f"  PGS测试项: {len(result.pgs_configs)} 个")
    print(f"  输出目录 : {output_dir}")
    print("=" * 60 + "\n")

    sys.exit(0)


def _generate_template(chip_type: str) -> None:
    """生成PinMapping填写模板"""
    templates = {
        "DIGITAL_74": [
            {"pin_no":1,  "pin_name":"1A",  "function":"输入1A",
             "direction":"IN",  "voltage_max":5.5,"notes":""},
            {"pin_no":2,  "pin_name":"1B",  "function":"输入1B",
             "direction":"IN",  "voltage_max":5.5,"notes":""},
            {"pin_no":3,  "pin_name":"1Y",  "function":"输出1Y",
             "direction":"OUT", "voltage_max":5.5,"notes":""},
            {"pin_no":7,  "pin_name":"GND", "function":"地",
             "direction":"GND", "voltage_max":0,  "notes":""},
            {"pin_no":14, "pin_name":"VCC", "function":"电源",
             "direction":"PWR", "voltage_max":5.5,"notes":""},
        ],
        "LDO": [
            {"pin_no":1,"pin_name":"VIN", "function":"输入电压",
             "direction":"IN", "voltage_max":40,"notes":""},
            {"pin_no":2,"pin_name":"GND", "function":"地",
             "direction":"GND","voltage_max":0, "notes":""},
            {"pin_no":3,"pin_name":"VOUT","function":"输出电压",
             "direction":"OUT","voltage_max":40,"notes":""},
        ],
        "EEPROM": [
            {"pin_no":1,"pin_name":"A0", "function":"地址位0",
             "direction":"IN",   "voltage_max":5.5,"notes":""},
            {"pin_no":2,"pin_name":"A1", "function":"地址位1",
             "direction":"IN",   "voltage_max":5.5,"notes":""},
            {"pin_no":3,"pin_name":"A2", "function":"地址位2",
             "direction":"IN",   "voltage_max":5.5,"notes":""},
            {"pin_no":4,"pin_name":"GND","function":"地",
             "direction":"GND",  "voltage_max":0,  "notes":""},
            {"pin_no":5,"pin_name":"SDA","function":"I2C数据",
             "direction":"BIDIR","voltage_max":5.5,"notes":"开漏"},
            {"pin_no":6,"pin_name":"SCL","function":"I2C时钟",
             "direction":"IN",   "voltage_max":5.5,"notes":""},
            {"pin_no":7,"pin_name":"WP", "function":"写保护",
             "direction":"IN",   "voltage_max":5.5,"notes":"低有效"},
            {"pin_no":8,"pin_name":"VCC","function":"电源",
             "direction":"PWR",  "voltage_max":5.5,"notes":""},
        ],
    }

    data     = templates.get(chip_type, templates["LDO"])
    out_path = Path(f"../data/raw/{chip_type}_PinMapping_Template.xlsx")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(data).to_excel(str(out_path), index=False)
    print(f"✅ 模板已生成: {out_path}")
    print(f"   填写完成后运行:")
    print(
        f"   python cli2.py --json <JSON路径> "
        f"--pins {out_path}"
    )


if __name__ == "__main__":
    main()
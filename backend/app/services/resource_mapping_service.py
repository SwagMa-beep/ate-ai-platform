"""
资源映射服务 - 模块二核心
根据chip_type自动选择适配器并生成完整映射
"""
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from app.models.resource_map import (
    PinInfo, ResourceMapping, PGSConfig, PGSDetailCondition,
    PinGroupConfig, AdapterInfo, ResourceMapResult,
    BOM_ANALOG_LDO, BOM_DUAL_LDO, BOM_DIGITAL,
    ADAPTER_MODELS, STS_PMU_VOLTAGE_RANGES, STS_PMU_CURRENT_RANGES
)
from app.models.testplan import ExtractionResult
from app.core.config import get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()


class ResourceMappingService:
    """
    资源映射服务
    联动模块一的ExtractionResult，自动生成模块二所有输出
    """

    def __init__(self):
        logger.info(" 资源映射服务初始化 [模块二]")

    # ============================================================
    # 主入口
    # ============================================================

    def generate_resource_map(
        self,
        extraction_result: ExtractionResult,
        pin_mapping_df: pd.DataFrame,
        dual_site: bool = False
    ) -> ResourceMapResult:
        """
        生成完整资源映射

        Args:
            extraction_result : 模块一的ExtractionResult对象
            pin_mapping_df    : 用户填写的PinMapping DataFrame
                                必须包含列: pin_no/pin_name/function/direction
            dual_site         : 是否使用双工位适配器(LDO场景)

        Returns:
            ResourceMapResult
        """
        chip_type  = extraction_result.chip_type
        chip_name  = extraction_result.chip_name

        logger.info(f" 开始资源映射 | 芯片: {chip_name} | 类型: {chip_type}")

        try:
            # Step1: 解析引脚信息
            pins = self._parse_pin_mapping(pin_mapping_df)

            # Step2: 选择适配器
            adapter_info = self._select_adapter(chip_type, pins, dual_site)

            # Step3: 分配STS8200S资源
            resource_mappings = self._allocate_resources(
                pins, chip_type, adapter_info, dual_site
            )

            # Step4: 生成PGS配置
            pgs_configs, pgs_details = self._generate_pgs_config(
                extraction_result, pins, resource_mappings, chip_type
            )

            # Step5: 生成引脚分组
            pin_groups = self._generate_pin_groups(pins, chip_name)

            return ResourceMapResult(
                status="success",
                chip_name=chip_name,
                chip_type=chip_type,
                adapter_model=adapter_info.adapter_model,
                resource_mappings=resource_mappings,
                pgs_configs=pgs_configs,
                pgs_detail_conditions=pgs_details,
                pin_groups=pin_groups,
                adapter_info=adapter_info,
            )

        except Exception as e:
            logger.error(f"❌ 资源映射失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return ResourceMapResult(
                status="error",
                chip_name=chip_name,
                chip_type=chip_type,
                errors=[f"资源映射失败: {str(e)}"]
            )

    # ============================================================
    # Step1: 解析PinMapping
    # ============================================================

    def _parse_pin_mapping(
        self, df: pd.DataFrame
    ) -> List[PinInfo]:
        """解析用户填写的PinMapping表"""
        pins = []
        required_cols = {"pin_no", "pin_name", "direction"}

        # 列名标准化（大小写/空格容错）
        df.columns = [c.strip().lower() for c in df.columns]
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"PinMapping缺少必要列: {missing}")

        for _, row in df.iterrows():
            try:
                pin = PinInfo(
                    pin_no    = int(row["pin_no"]),
                    pin_name  = str(row["pin_name"]).strip(),
                    function  = str(row.get("function", "")).strip(),
                    direction = str(row.get("direction", "IN")).upper().strip(),
                    voltage_max = float(row["voltage_max"])
                        if "voltage_max" in row and pd.notna(row["voltage_max"])
                        else None,
                    current_max = float(row["current_max"])
                        if "current_max" in row and pd.notna(row["current_max"])
                        else None,
                    notes = str(row.get("notes", "")).strip(),
                )
                pins.append(pin)
            except Exception as e:
                logger.warning(f"⚠️ 引脚 {row.get('pin_no')} 解析失败: {e}")

        logger.info(f" 解析到 {len(pins)} 个引脚")
        return pins

    # ============================================================
    # Step2: 选择适配器
    # ============================================================

    def _select_adapter(
        self,
        chip_type: str,
        pins: List[PinInfo],
        dual_site: bool
    ) -> AdapterInfo:
        """根据chip_type选择适配器模板"""

        pin_count = len(pins)

        if chip_type in {"DIGITAL_74", "DIGITAL_54", "DIGITAL_4000", "MEMORY"}:
            return AdapterInfo(
                adapter_model = ADAPTER_MODELS["DIGITAL"],
                chip_type     = chip_type,
                socket_type   = "ZIF14（14引脚锁紧座）",
                max_pin_count = 14,
                vi_channels   = ["FH0", "SH0"],
                dio_channels  = [f"DIO{i}" for i in range(12)],
                cbit_channels = ["CBIT0", "CBIT1"],
                tmu_channels  = ["TMUA", "TMUB"],
                bom_items     = BOM_DIGITAL,
                notes=(
                    "适用14引脚以内数字逻辑芯片。\n"
                    "BUF634提供高速时序缓冲，51Ω匹配电阻防反射。\n"
                    "K1控制VDD供电，K2控制VSS。"
                )
            )

        elif chip_type == "LDO" and dual_site:
            return AdapterInfo(
                adapter_model = ADAPTER_MODELS["LDO_DUAL"],
                chip_type     = chip_type,
                socket_type   = "ZIF14（双工位）",
                max_pin_count = 14,
                vi_channels   = ["FH0","SH0","FH1","SH1",
                                  "FH4","SH4","FH5","SH5"],
                dio_channels  = [],
                cbit_channels = ["CBIT0", "CBIT1"],
                tmu_channels  = ["TMUB"],
                bom_items     = BOM_DUAL_LDO,
                notes=(
                    "双工位并行测试。\n"
                    "工位1: FH0/SH0=VOUT, FH1/SH1=VIN, CBIT0=K1\n"
                    "工位2: FH4/SH4=VOUT, FH5/SH5=VIN, CBIT1=K2"
                )
            )

        elif chip_type in {"LDO", "EEPROM", "ANALOG_GENERAL"}:
            return AdapterInfo(
                adapter_model = ADAPTER_MODELS["LDO"],
                chip_type     = chip_type,
                socket_type   = "SOP8（IC-SOCKET-SOP8-5.4）",
                max_pin_count = 8,
                vi_channels   = ["FH0","SH0","FH1","SH1",
                                  "FH3","SH3","FH5","SH5","FH6","SH6"],
                dio_channels  = [],
                cbit_channels = ["CBIT0","CBIT1","CBIT2","CBIT3"],
                tmu_channels  = ["TMUA", "TMUB"],
                bom_items     = BOM_ANALOG_LDO,
                notes=(
                    "适用SOP8封装模拟芯片。\n"
                    "EL7156提供高性能驱动，BAV99提供ESD保护。\n"
                    "CBIT0~2控制K1~K3继电器，CBIT3控制EL7156使能。"
                )
            )

        else:
            # 默认使用模拟适配器
            logger.warning(f"⚠️ 未知芯片类型 {chip_type}，使用通用模拟适配器")
            return AdapterInfo(
                adapter_model = ADAPTER_MODELS["LDO"],
                chip_type     = "UNKNOWN",
                socket_type   = "SOP8",
                max_pin_count = 8,
                vi_channels   = ["FH0","SH0","FH1","SH1"],
                dio_channels  = [],
                cbit_channels = ["CBIT0","CBIT1","CBIT2"],
                tmu_channels  = ["TMUA"],
                bom_items     = BOM_ANALOG_LDO,
                notes         = "未知芯片类型，使用通用模拟适配器，请手动确认资源分配。"
            )

    # ============================================================
    # Step3: 分配STS8200S资源
    # ============================================================

    def _allocate_resources(
        self,
        pins: List[PinInfo],
        chip_type: str,
        adapter: AdapterInfo,
        dual_site: bool
    ) -> List[ResourceMapping]:
        """根据芯片类型和引脚方向自动分配STS8200S资源"""

        if chip_type in {"DIGITAL_74", "DIGITAL_54", "DIGITAL_4000", "MEMORY"}:
            return self._allocate_digital(pins, adapter)
        elif chip_type == "LDO" and dual_site:
            return self._allocate_ldo_dual(pins, adapter)
        elif chip_type == "LDO":
            return self._allocate_ldo(pins, adapter)
        elif chip_type == "EEPROM":
            return self._allocate_eeprom(pins, adapter)
        else:
            return self._allocate_general(pins, adapter)

    def _allocate_digital(
        self, pins: List[PinInfo], adapter: AdapterInfo
    ) -> List[ResourceMapping]:
        """场景A：数字芯片资源分配"""
        mappings = []
        dio_idx  = 0

        for pin in pins:
            name_up = pin.pin_name.upper()

            # VCC/VDD → FH0/SH0
            if pin.direction in {"PWR"} or name_up in {"VCC","VDD","V+"}:
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = pin.function,
                    direction    = pin.direction,
                    sts_resource = "FH0/SH0",
                    resource_type= "FH_SH",
                    channel_no   = 0,
                    force_mode   = "ForceV",
                    measure_mode = "MeasureI",
                    voltage_range= "±5V",
                    current_range= "±100mA",
                    notes        = "VCC四线开尔文测量，K1继电器(CBIT0)控制通断"
                ))

            # GND → GND轨
            elif pin.direction == "GND" or name_up in {"GND","VSS","AGND"}:
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = pin.function,
                    direction    = pin.direction,
                    sts_resource = "GND",
                    resource_type= "GND",
                    channel_no   = -1,
                    force_mode   = "",
                    measure_mode = "",
                    voltage_range= "",
                    current_range= "",
                    notes        = "接地引脚，连接AGND"
                ))

            # 信号引脚 → DIO
            elif dio_idx < 12:
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = pin.function,
                    direction    = pin.direction,
                    sts_resource = f"DIO{dio_idx}",
                    resource_type= "DIO",
                    channel_no   = dio_idx,
                    force_mode   = "DIO_Drive" if pin.direction == "IN" else "",
                    measure_mode = "DIO_Sense" if pin.direction == "OUT" else "",
                    voltage_range= "-1.5V~6.5V",
                    current_range= "",
                    notes        = (
                        f"引脚{pin.pin_no}({pin.pin_name}) → DIO{dio_idx}，"
                        f"经BUF634缓冲后连接TMUA/TMUB"
                        if pin.direction == "OUT" else
                        f"引脚{pin.pin_no}({pin.pin_name}) → DIO{dio_idx}"
                    )
                ))
                dio_idx += 1
            else:
                logger.warning(
                    f"⚠️ 引脚 {pin.pin_no}({pin.pin_name}) DIO通道已满，标记为NC"
                )
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = pin.function,
                    direction    = pin.direction,
                    sts_resource = "NC",
                    resource_type= "NC",
                    channel_no   = -1,
                    notes        = "DIO通道已满，此引脚未连接"
                ))

        return mappings

    def _allocate_ldo(
        self, pins: List[PinInfo], adapter: AdapterInfo
    ) -> List[ResourceMapping]:
        """场景B1：LDO资源分配"""
        mappings = []

        for pin in pins:
            name_up = pin.pin_name.upper()

            if name_up in {"VIN", "IN", "INPUT", "VI"}:
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = "输入电压",
                    direction    = "IN",
                    sts_resource = "FH0/SH0",
                    resource_type= "FH_SH",
                    channel_no   = 0,
                    force_mode   = "ForceV",
                    measure_mode = "MeasureI",
                    voltage_range= "±10V",
                    current_range= "±100mA",
                    notes        = "VIN四线开尔文，CBIT0(K1)控制主路继电器"
                ))

            elif name_up in {"VOUT","OUT","OUTPUT","VO","VOUT1"}:
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = "输出电压",
                    direction    = "OUT",
                    sts_resource = "FH1/SH1",
                    resource_type= "FH_SH",
                    channel_no   = 1,
                    force_mode   = "ForceI",
                    measure_mode = "MeasureV",
                    voltage_range= "±5V",
                    current_range= "±100mA",
                    notes        = "VOUT四线开尔文测量，CBIT1(K2)控制输出继电器"
                ))

            elif name_up in {"EN","ENABLE","ENB","SHDN"}:
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = "使能控制",
                    direction    = "IN",
                    sts_resource = "CBIT2",
                    resource_type= "CBIT",
                    channel_no   = 2,
                    force_mode   = "Digital",
                    measure_mode = "",
                    voltage_range= "",
                    current_range= "",
                    notes        = "EN引脚由CBIT2(K3继电器)控制高低电平"
                ))

            elif name_up in {"GND","AGND","PGND","VSS","EP"}:
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = "地",
                    direction    = "GND",
                    sts_resource = "AGND",
                    resource_type= "GND",
                    channel_no   = -1,
                    notes        = "接模拟地AGND"
                ))

            elif name_up in {"ADJ","TRIM","FB","SENSE"}:
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = "调节/反馈",
                    direction    = "IN",
                    sts_resource = "FH3/SH3",
                    resource_type= "FH_SH",
                    channel_no   = 3,
                    force_mode   = "ForceV",
                    measure_mode = "MeasureV",
                    voltage_range= "±5V",
                    current_range= "±1mA",
                    notes        = "ADJ/SENSE引脚，接FH3/SH3辅助通道"
                ))

            else:
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = pin.function,
                    direction    = pin.direction,
                    sts_resource = "NC",
                    resource_type= "NC",
                    channel_no   = -1,
                    notes        = f"引脚{pin.pin_name}未自动识别，请手动分配资源"
                ))

        return mappings

    def _allocate_ldo_dual(
        self, pins: List[PinInfo], adapter: AdapterInfo
    ) -> List[ResourceMapping]:
        """场景B2：双工位LDO（两套资源）"""
        mappings = []

        # 工位1
        for site, vi_in, vi_out, cbit in [
            (1, "FH1/SH1", "FH0/SH0", "CBIT0"),
            (2, "FH5/SH5", "FH4/SH4", "CBIT1"),
        ]:
            for pin in pins:
                name_up = pin.pin_name.upper()
                if name_up in {"VIN","IN","INPUT"}:
                    mappings.append(ResourceMapping(
                        pin_no       = pin.pin_no,
                        pin_name     = pin.pin_name,
                        function     = f"工位{site} VIN",
                        direction    = "IN",
                        sts_resource = vi_in,
                        resource_type= "FH_SH",
                        channel_no   = 1 if site == 1 else 5,
                        force_mode   = "ForceV",
                        measure_mode = "MeasureI",
                        voltage_range= "±10V",
                        current_range= "±100mA",
                        notes        = f"工位{site} VIN供电"
                    ))
                elif name_up in {"VOUT","OUT","OUTPUT"}:
                    mappings.append(ResourceMapping(
                        pin_no       = pin.pin_no,
                        pin_name     = pin.pin_name,
                        function     = f"工位{site} VOUT",
                        direction    = "OUT",
                        sts_resource = vi_out,
                        resource_type= "FH_SH",
                        channel_no   = 0 if site == 1 else 4,
                        force_mode   = "ForceI",
                        measure_mode = "MeasureV",
                        voltage_range= "±5V",
                        current_range= "±100mA",
                        notes        = f"工位{site} VOUT测量"
                    ))
                elif name_up in {"GND","AGND","VSS"}:
                    mappings.append(ResourceMapping(
                        pin_no       = pin.pin_no,
                        pin_name     = pin.pin_name,
                        function     = f"工位{site} GND",
                        direction    = "GND",
                        sts_resource = "AGND",
                        resource_type= "GND",
                        channel_no   = -1,
                        notes        = f"工位{site} 接AGND"
                    ))

        return mappings

    def _allocate_eeprom(
        self, pins: List[PinInfo], adapter: AdapterInfo
    ) -> List[ResourceMapping]:
        """场景EEPROM资源分配"""
        mappings = []
        dio_idx  = 0
        fh_idx   = 0

        for pin in pins:
            name_up = pin.pin_name.upper()

            if name_up in {"SCL","CLK","CLOCK"}:
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = "I2C时钟",
                    direction    = "IN",
                    sts_resource = f"DIO{dio_idx}",
                    resource_type= "DIO",
                    channel_no   = dio_idx,
                    force_mode   = "DIO_Drive",
                    measure_mode = "",
                    voltage_range= "0~5.5V",
                    current_range= "",
                    notes        = "SCL时钟线，DIO模拟I2C时序"
                ))
                dio_idx += 1

            elif name_up in {"SDA","DATA"}:
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = "I2C数据",
                    direction    = "BIDIR",
                    sts_resource = f"DIO{dio_idx}",
                    resource_type= "DIO",
                    channel_no   = dio_idx,
                    force_mode   = "DIO_Drive",
                    measure_mode = "DIO_Sense",
                    voltage_range= "0~5.5V",
                    current_range= "",
                    notes        = "SDA数据线，双向，DIO模拟I2C"
                ))
                dio_idx += 1

            elif name_up in {"VCC","VDD","V+"}:
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = "电源",
                    direction    = "PWR",
                    sts_resource = f"FH{fh_idx}/SH{fh_idx}",
                    resource_type= "FH_SH",
                    channel_no   = fh_idx,
                    force_mode   = "ForceV",
                    measure_mode = "MeasureI",
                    voltage_range= "±5V",
                    current_range= "±10mA",
                    notes        = "VCC电源，由VI源提供"
                ))
                fh_idx += 1

            elif name_up in {"GND","VSS"}:
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = "地",
                    direction    = "GND",
                    sts_resource = "AGND",
                    resource_type= "GND",
                    channel_no   = -1,
                    notes        = "接模拟地"
                ))

            elif name_up in {"WP","WRITE_PROTECT"}:
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = "写保护",
                    direction    = "IN",
                    sts_resource = "CBIT0",
                    resource_type= "CBIT",
                    channel_no   = 0,
                    force_mode   = "Digital",
                    measure_mode = "",
                    notes        = "WP写保护引脚，CBIT0控制高低"
                ))

            elif name_up in {"A0","A1","A2"}:
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = "地址位",
                    direction    = "IN",
                    sts_resource = f"DIO{dio_idx}",
                    resource_type= "DIO",
                    channel_no   = dio_idx,
                    force_mode   = "DIO_Drive",
                    measure_mode = "",
                    notes        = f"I2C地址位{name_up}，接DIO{dio_idx}"
                ))
                dio_idx += 1

            else:
                mappings.append(ResourceMapping(
                    pin_no       = pin.pin_no,
                    pin_name     = pin.pin_name,
                    function     = pin.function,
                    direction    = pin.direction,
                    sts_resource = "NC",
                    resource_type= "NC",
                    channel_no   = -1,
                    notes        = "未识别引脚，请手动分配"
                ))

        return mappings

    def _allocate_general(
        self, pins: List[PinInfo], adapter: AdapterInfo
    ) -> List[ResourceMapping]:
        """通用分配（未知芯片类型）"""
        mappings = []
        fh_idx = 0

        for pin in pins:
            name_up = pin.pin_name.upper()

            if pin.direction == "GND" or name_up in {"GND","VSS","AGND"}:
                res = "AGND"
                rtype = "GND"
                notes = "地引脚"
            elif pin.direction == "PWR" or name_up in {"VCC","VDD","VIN","VOUT"}:
                res   = f"FH{fh_idx}/SH{fh_idx}"
                rtype = "FH_SH"
                notes = f"电源/信号引脚，分配FH{fh_idx}/SH{fh_idx}"
                fh_idx = min(fh_idx + 1, 7)
            else:
                res   = "NC"
                rtype = "NC"
                notes = "请手动分配资源"

            mappings.append(ResourceMapping(
                pin_no       = pin.pin_no,
                pin_name     = pin.pin_name,
                function     = pin.function,
                direction    = pin.direction,
                sts_resource = res,
                resource_type= rtype,
                channel_no   = fh_idx - 1 if rtype == "FH_SH" else -1,
                notes        = notes
            ))

        return mappings

    # ============================================================
    # Step4: 生成PGS配置
    # ============================================================

    def _generate_pgs_config(
        self,
        extraction_result: ExtractionResult,
        pins: List[PinInfo],
        resource_mappings: List[ResourceMapping],
        chip_type: str
    ) -> Tuple[List[PGSConfig], List[PGSDetailCondition]]:
        """根据chip_type生成对应的PGS填表配置"""

        if chip_type in {"DIGITAL_74","DIGITAL_54","DIGITAL_4000","MEMORY"}:
            return self._pgs_digital(
                extraction_result, pins, resource_mappings
            )
        elif chip_type == "LDO":
            return self._pgs_ldo(extraction_result, resource_mappings)
        elif chip_type == "EEPROM":
            return self._pgs_eeprom(extraction_result, resource_mappings)
        else:
            return self._pgs_general(extraction_result, resource_mappings)

    def _pgs_digital(
        self,
        result: ExtractionResult,
        pins: List[PinInfo],
        mappings: List[ResourceMapping]
    ) -> Tuple[List[PGSConfig], List[PGSDetailCondition]]:
        """数字芯片PGS配置生成"""
        configs  = []
        details  = []
        test_id  = 1

        chip_name = result.chip_name

        # 引脚分组字符串
        all_pins = [p.pin_name for p in pins]
        in_pins  = [p.pin_name for p in pins if p.direction == "IN"]
        out_pins = [p.pin_name for p in pins if p.direction == "OUT"]
        in_str   = ",".join(in_pins)
        out_str  = ",".join(out_pins)
        all_str  = ",".join(all_pins)

        # ── 0. GlobalVariable ────────────────────────────────
        configs.append(PGSConfig(
            test_id       = 0,
            test_name     = "GlobalVariable",
            function_type = "GlobalVariable",
            vector_file   = f"{chip_name}.vecdio",
            all_group     = all_str,
            in_group      = in_str,
            out_group     = out_str,
            notes         = "全局变量配置，向量文件名和引脚分组"
        ))
        details.append(PGSDetailCondition(
            test_name      = "GlobalVariable",
            param_name     = "-",
            condition_key  = "VECTOR_FILE",
            condition_value= f"{chip_name}.vecdio",
            notes          = "向量文件名，与工程目录下.vecdio文件一致"
        ))
        details.append(PGSDetailCondition(
            test_name      = "GlobalVariable",
            param_name     = "-",
            condition_key  = "AllGroup",
            condition_value= all_str,
            notes          = "所有引脚按顺序列出（对应PGS管脚列表）"
        ))
        details.append(PGSDetailCondition(
            test_name      = "GlobalVariable",
            param_name     = "-",
            condition_key  = "INGroup",
            condition_value= in_str,
            notes          = "输入引脚组（施加激励）"
        ))
        details.append(PGSDetailCondition(
            test_name      = "GlobalVariable",
            param_name     = "-",
            condition_key  = "OutGroup",
            condition_value= out_str,
            notes          = "输出引脚组（采集响应）"
        ))

        # ── 1. CON_N（连接性测试）────────────────────────────
        configs.append(PGSConfig(
            test_id       = test_id,
            test_name     = "CON_N",
            function_type = "FIMV_PMU",
            select_group  = "AllGroup",
            test_pins     = all_str,
            pmu_value     = 100.0,
            pmu_irang     = "PMU_IRANG_100UA",
            pmu_vrang     = "PMU_VRANG_5V",
            limit_min     = -1.0,
            limit_max     = 1.0,
            limit_unit    = "V",
            notes         = "连接性测试，±100μA，检测引脚是否电气连通"
        ))
        for k, v, u, n in [
            ("SELECT_GROUP", "AllGroup",          "",  "选择全部引脚"),
            ("PMU_VALUE",    "100",               "μA","恒流源±100μA"),
            ("PMU_IRANG",    "PMU_IRANG_100UA",   "",  "电流量程100μA"),
            ("PMU_VRANG",    "PMU_VRANG_5V",      "",  "电压量程5V"),
            ("LIMIT_MIN",    "-1.0",              "V", "下限-1V"),
            ("LIMIT_MAX",    "1.0",               "V", "上限1V"),
        ]:
            details.append(PGSDetailCondition(
                test_name="CON_N", param_name="CONNECT",
                condition_key=k, condition_value=v,
                condition_unit=u, notes=n
            ))
        test_id += 1

        # ── 2. FUN_T（功能测试）─────────────────────────────
        configs.append(PGSConfig(
            test_id       = test_id,
            test_name     = "FUN_T",
            function_type = "FUNCTION",
            vcc_value     = 5.0,
            vcc_vrang     = "5V",
            vcc_irang     = "100mA",
            start_label   = "FUN_START",
            stop_label    = "FUN_STOP",
            vih           = 3.5,
            vil           = 1.5,
            voh           = 2.7,
            vol           = 0.5,
            notes         = "功能测试，需配合.vecdio向量文件"
        ))
        for k, v, u, n in [
            ("VCC_VALUE1",  "5.0",        "V",  "VCC供电电压"),
            ("VCC_VRANG1",  "5V",         "",   "VCC电压量程档"),
            ("VCC_IRANG1",  "100mA",      "",   "VCC电流量程档"),
            ("STARTLABLE",  "FUN_START",  "",   "向量起始Label"),
            ("STOPLABLE",   "FUN_STOP",   "",   "向量结束Label"),
            ("VIH",         "3.5",        "V",  "输入高电平判定"),
            ("VIL",         "1.5",        "V",  "输入低电平判定"),
            ("VOH",         "2.7",        "V",  "输出高电平判定"),
            ("VOL",         "0.5",        "V",  "输出低电平判定"),
        ]:
            details.append(PGSDetailCondition(
                test_name="FUN_T", param_name="FUN",
                condition_key=k, condition_value=v,
                condition_unit=u, notes=n
            ))
        test_id += 1

        # ── 3. VOH_T（输出高电平）───────────────────────────
        configs.append(PGSConfig(
            test_id       = test_id,
            test_name     = "VOH_T",
            function_type = "FIMV_PMU",
            vcc_value     = 5.0,
            vcc_vrang     = "5V",
            vcc_irang     = "100mA",
            select_group  = "OutGroup",
            test_pins     = out_str,
            pmu_value     = -0.4,
            pmu_irang     = "PMU_IRANG_1MA",
            pmu_vrang     = "PMU_VRANG_5V",
            limit_min     = 2.7,
            limit_max     = 5.5,
            limit_unit    = "V",
            notes         = "恒流测压，IOH=-0.4mA，测VOUT≥2.7V"
        ))
        for k, v, u, n in [
            ("SELECT_GROUP","OutGroup",       "",  "测输出引脚"),
            ("PMU_VALUE",   "-0.4",           "mA","拉电流-0.4mA"),
            ("PMU_IRANG",   "PMU_IRANG_1MA",  "",  "电流量程1mA"),
            ("PMU_VRANG",   "PMU_VRANG_5V",   "",  "电压量程5V"),
            ("LIMIT_MIN",   "2.7",            "V", "VOH下限2.7V"),
            ("LIMIT_MAX",   "5.5",            "V", "VOH上限5.5V"),
        ]:
            details.append(PGSDetailCondition(
                test_name="VOH_T", param_name="VOH",
                condition_key=k, condition_value=v,
                condition_unit=u, notes=n
            ))
        test_id += 1

        # ── 4. VOL_T（输出低电平）───────────────────────────
        configs.append(PGSConfig(
            test_id       = test_id,
            test_name     = "VOL_T",
            function_type = "FIMV_PMU",
            vcc_value     = 5.0,
            vcc_vrang     = "5V",
            vcc_irang     = "100mA",
            select_group  = "OutGroup",
            test_pins     = out_str,
            pmu_value     = 4.0,
            pmu_irang     = "PMU_IRANG_10MA",
            pmu_vrang     = "PMU_VRANG_5V",
            limit_min     = 0.0,
            limit_max     = 0.5,
            limit_unit    = "V",
            notes         = "恒流测压，IOL=4mA，测VOUT≤0.5V"
        ))
        for k, v, u, n in [
            ("SELECT_GROUP","OutGroup",        "",  "测输出引脚"),
            ("PMU_VALUE",   "4.0",             "mA","灌电流4mA"),
            ("PMU_IRANG",   "PMU_IRANG_10MA",  "",  "电流量程10mA"),
            ("PMU_VRANG",   "PMU_VRANG_5V",    "",  "电压量程5V"),
            ("LIMIT_MIN",   "0.0",             "V", "VOL下限0V"),
            ("LIMIT_MAX",   "0.5",             "V", "VOL上限0.5V"),
        ]:
            details.append(PGSDetailCondition(
                test_name="VOL_T", param_name="VOL",
                condition_key=k, condition_value=v,
                condition_unit=u, notes=n
            ))
        test_id += 1

        # ── 5. IIH_T（输入高电平漏电流）────────────────────
        configs.append(PGSConfig(
            test_id       = test_id,
            test_name     = "IIH_T",
            function_type = "FVMI_PMU",
            vcc_value     = 5.0,
            vcc_vrang     = "5V",
            vcc_irang     = "100mA",
            select_group  = "INGroup",
            test_pins     = in_str,
            pmu_value     = 2.7,
            pmu_vrang     = "PMU_VRANG_10V",
            pmu_irang     = "PMU_IRANG_100UA",
            limit_min     = -1.0,
            limit_max     = 20.0,
            limit_unit    = "μA",
            notes         = "恒压测流，VIH=2.7V，测输入漏电流≤20μA"
        ))
        for k, v, u, n in [
            ("SELECT_GROUP","INGroup",         "",  "测输入引脚"),
            ("PMU_VALUE",   "2.7",             "V", "施加VIH=2.7V"),
            ("PMU_VRANG",   "PMU_VRANG_10V",   "",  "电压量程10V"),
            ("PMU_IRANG",   "PMU_IRANG_100UA", "",  "电流量程100μA"),
            ("LIMIT_MIN",   "-1.0",            "μA","下限-1μA"),
            ("LIMIT_MAX",   "20.0",            "μA","上限20μA"),
        ]:
            details.append(PGSDetailCondition(
                test_name="IIH_T", param_name="IIH",
                condition_key=k, condition_value=v,
                condition_unit=u, notes=n
            ))
        test_id += 1

        # ── 6. IIL_T（输入低电平漏电流）────────────────────
        configs.append(PGSConfig(
            test_id       = test_id,
            test_name     = "IIL_T",
            function_type = "FVMI_PMU",
            vcc_value     = 5.0,
            vcc_vrang     = "5V",
            vcc_irang     = "100mA",
            select_group  = "INGroup",
            test_pins     = in_str,
            pmu_value     = 0.4,
            pmu_vrang     = "PMU_VRANG_10V",
            pmu_irang     = "PMU_IRANG_100UA",
            limit_min     = -400.0,
            limit_max     = 0.0,
            limit_unit    = "μA",
            notes         = "恒压测流，VIL=0.4V，测输入低电平漏电流"
        ))
        test_id += 1

        # ── 7. ICC_T（电源电流）─────────────────────────────
        configs.append(PGSConfig(
            test_id       = test_id,
            test_name     = "ICC_T",
            function_type = "SUPPLY",
            vcc_value     = 5.0,
            vcc_vrang     = "5V",
            vcc_irang     = "100mA",
            select_vcc    = "VCC1",
            open_channel  = "DisConnect",
            open_pins_group= "OutGroup",
            limit_min     = 0.0,
            limit_max     = 80.0,
            limit_unit    = "mA",
            notes         = "电源电流测试，输出断开，测VCC静态电流"
        ))
        for k, v, u, n in [
            ("SelectVCC",      "VCC1",       "",   "选择VCC1"),
            ("OpenChannel",    "DisConnect", "",   "输出引脚断开"),
            ("OpenPinsGroup",  "OutGroup",   "",   "断开输出引脚组"),
            ("LIMIT_MIN",      "0.0",        "mA", "电流下限0mA"),
            ("LIMIT_MAX",      "80.0",       "mA", "电流上限80mA"),
        ]:
            details.append(PGSDetailCondition(
                test_name="ICC_T", param_name="ICCH/ICCL",
                condition_key=k, condition_value=v,
                condition_unit=u, notes=n
            ))
        test_id += 1

        return configs, details

    def _pgs_ldo(
        self,
        result: ExtractionResult,
        mappings: List[ResourceMapping]
    ) -> Tuple[List[PGSConfig], List[PGSDetailCondition]]:
        """LDO PGS配置生成"""
        configs = []
        details = []
        test_id = 1

        # ── VO测试 ───────────────────────────────────────────
        configs.append(PGSConfig(
            test_id       = test_id,
            test_name     = "VO_T",
            function_type = "FIMV_PMU",
            vcc_value     = 10.0,
            vcc_vrang     = "10V",
            vcc_irang     = "100mA",
            pmu_value     = 500.0,
            pmu_irang     = "PMU_IRANG_1MA",
            pmu_vrang     = "PMU_VRANG_10V",
            limit_min     = 4.75,
            limit_max     = 5.25,
            limit_unit    = "V",
            notes         = "输出电压测试，VIN=10V，IOUT=500mA，测VOUT=5V±5%"
        ))
        for k, v, u, n in [
            ("VCC_VALUE",  "10.0",           "V",  "VIN=10V"),
            ("PMU_VALUE",  "500",             "mA", "负载电流500mA"),
            ("PMU_IRANG",  "PMU_IRANG_1MA",  "",   "⚠️ 实际500mA需确认量程"),
            ("PMU_VRANG",  "PMU_VRANG_10V",  "",   "电压量程10V"),
            ("LIMIT_MIN",  "4.75",           "V",  "VOUT下限4.75V"),
            ("LIMIT_MAX",  "5.25",           "V",  "VOUT上限5.25V"),
        ]:
            details.append(PGSDetailCondition(
                test_name="VO_T", param_name="VO",
                condition_key=k, condition_value=v,
                condition_unit=u, notes=n
            ))
        test_id += 1

        # ── Iq测试 ───────────────────────────────────────────
        configs.append(PGSConfig(
            test_id       = test_id,
            test_name     = "Iq_T",
            function_type = "FVMI_PMU",
            vcc_value     = 10.0,
            vcc_vrang     = "10V",
            vcc_irang     = "10mA",
            pmu_value     = 10.0,
            pmu_vrang     = "PMU_VRANG_10V",
            pmu_irang     = "PMU_IRANG_10MA",
            limit_min     = 0.0,
            limit_max     = 8.0,
            limit_unit    = "mA",
            notes         = "静态电流测试，无负载，QTMU精密测量"
        ))
        test_id += 1

        # ── Sv测试 ───────────────────────────────────────────
        configs.append(PGSConfig(
            test_id       = test_id,
            test_name     = "Sv_T",
            function_type = "FIMV_PMU",
            vcc_value     = 7.0,
            vcc_vrang     = "10V",
            vcc_irang     = "100mA",
            pmu_value     = 500.0,
            pmu_irang     = "PMU_IRANG_1MA",
            pmu_vrang     = "PMU_VRANG_10V",
            limit_min     = 0.0,
            limit_max     = 50.0,
            limit_unit    = "mV",
            notes         = "电压调整率，VIN从7V到25V，测ΔVOUT≤50mV"
        ))
        test_id += 1

        # ── Si测试 ───────────────────────────────────────────
        configs.append(PGSConfig(
            test_id       = test_id,
            test_name     = "Si_T",
            function_type = "FIMV_PMU",
            vcc_value     = 10.0,
            vcc_vrang     = "10V",
            vcc_irang     = "100mA",
            pmu_value     = 5.0,
            pmu_irang     = "PMU_IRANG_10MA",
            pmu_vrang     = "PMU_VRANG_10V",
            limit_min     = 0.0,
            limit_max     = 100.0,
            limit_unit    = "mV",
            notes         = "负载调整率，IOUT从5mA到1.5A，测ΔVOUT≤100mV"
        ))
        test_id += 1

        return configs, details

    def _pgs_eeprom(
        self,
        result: ExtractionResult,
        mappings: List[ResourceMapping]
    ) -> Tuple[List[PGSConfig], List[PGSDetailCondition]]:
        """EEPROM PGS配置生成"""
        configs = []
        details = []
        test_id = 1

        for test_name, data, label_s, label_e, note in [
            ("WRITE_READ_55", "0x55",
             "WR55_START", "WR55_STOP", "写入0x55并回读验证"),
            ("WRITE_READ_AA", "0xAA",
             "WRAA_START", "WRAA_STOP", "写入0xAA并回读验证"),
            ("WRITE_READ_DIFF", "0x00/0xFF/0xA5",
             "WRDIFF_START", "WRDIFF_STOP", "写入不同数据模式并回读验证"),
        ]:
            configs.append(PGSConfig(
                test_id       = test_id,
                test_name     = test_name,
                function_type = "FUNCTION",
                vcc_value     = 5.0,
                vcc_vrang     = "5V",
                vcc_irang     = "10mA",
                start_label   = label_s,
                stop_label    = label_e,
                vih           = 3.5,
                vil           = 0.5,
                voh           = 3.0,
                vol           = 0.4,
                notes         = note
            ))
            test_id += 1

        return configs, details

    def _pgs_general(
        self,
        result: ExtractionResult,
        mappings: List[ResourceMapping]
    ) -> Tuple[List[PGSConfig], List[PGSDetailCondition]]:
        """通用PGS配置（未知芯片类型）"""
        configs = [PGSConfig(
            test_id       = 0,
            test_name     = "GlobalVariable",
            function_type = "GlobalVariable",
            vector_file   = f"{result.chip_name}.vecdio",
            notes         = "请根据实际芯片类型手动填写测试项"
        )]
        return configs, []

    # ============================================================
    # Step5: 生成引脚分组
    # ============================================================

    def _generate_pin_groups(
        self, pins: List[PinInfo], chip_name: str
    ) -> PinGroupConfig:
        """生成GlobalVariable引脚分组"""
        all_group = [p.pin_name for p in pins]
        in_group  = [p.pin_name for p in pins if p.direction == "IN"]
        out_group = [p.pin_name for p in pins if p.direction == "OUT"]
        pwr_group = [p.pin_name for p in pins if p.direction == "PWR"]
        gnd_group = [p.pin_name for p in pins if p.direction == "GND"]

        return PinGroupConfig(
            chip_name   = chip_name,
            pin_count   = len(pins),
            all_group   = all_group,
            in_group    = in_group,
            out_group   = out_group,
            pwr_group   = pwr_group,
            gnd_group   = gnd_group,
            vector_file = f"{chip_name}.vecdio"
        )
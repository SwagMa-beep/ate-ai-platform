"""
数据模型定义 - 面向STS8200S测试平台
支持三种测试场景：
  - 场景A: 数字芯片测试 (74系列/54系列/4000系列)
  - 场景B: 模拟芯片测试 (L7805CV线性稳压器 / AT24C01 EEPROM)
  - 场景C: 通用模拟芯片测试
"""
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Literal


# ============================================================
# STS8200S 硬件资源常量
# ============================================================

STS8200S_VI_CHANNELS = [f"FVI{i}" for i in range(8)]
STS8200S_DIO_CHANNELS = [f"D{i}" for i in range(24)]
STS8200S_CBIT_CHANNELS = [f"CBIT{i}" for i in range(40)]

STS8200S_LIMITS = {
    "VI_voltage_max":  10.0,
    "VI_current_max":  0.2,
    "DIO_voltage_high": 5.5,
    "DIO_voltage_low": -0.5,
}

DIGITAL_DC_PARAMS = {
    "CONNECT", "FUN",
    "VIH", "VIL",
    "VOH", "VOL",
    "VIK",
    "II", "IIH", "IIL",
    "IOZH", "IOZL",
    "IOH", "IOL",
    "IOS",
    "ICCH", "ICCL",
    "Ron", "DeltaRon",
}

DIGITAL_AC_PARAMS = {
    "Tr", "tTLH",
    "Tf", "tTHL",
    "tPHL",
    "tPLH",
}

LDO_PARAMS = {
    "VO", "Sv", "Si", "Iq",
}

EEPROM_PARAMS = {
    "READ_55", "WRITE_55",
    "READ_AA", "WRITE_AA",
    "READ_DIFF", "WRITE_DIFF",
}


# ============================================================
# 新增：引脚定义模型
# ============================================================

class PinDefinition(BaseModel):
    """芯片引脚定义 - 从Datasheet引脚表自动提取"""
    pin_no: int = Field(
        ...,
        description="引脚编号(整数，从1开始)"
    )
    pin_name: str = Field(
        ...,
        description="引脚名称，如1A/VCC/GND/SDA"
    )
    function: str = Field(
        default="",
        description="引脚功能描述"
    )
    direction: Literal[
        "IN", "OUT", "PWR", "GND", "BIDIR", "NC"
    ] = Field(
        default="IN",
        description="引脚方向：IN/OUT/PWR/GND/BIDIR/NC"
    )
    voltage_max: Optional[float] = Field(
        None,
        description="最大电压(V)"
    )
    current_max: Optional[float] = Field(
        None,
        description="最大电流(A)"
    )
    notes: str = Field(
        default="",
        description="备注，如开漏输出/低有效"
    )


# ============================================================
# 通用基础模型
# ============================================================

class STSResourceMapping(BaseModel):
    """STS8200S 硬件资源映射"""
    vi_channel: Optional[str] = Field(
        None,
        description="VI源通道, 如 FVI0~FVI7"
    )
    dio_channels: List[str] = Field(
        default_factory=list,
        description="DIO数字通道列表, 如 [D0, D1, ...]"
    )
    cbit_channels: List[str] = Field(
        default_factory=list,
        description="CBIT继电器控制通道"
    )
    vcc_pin: Optional[str] = Field(
        None,
        description="VCC供电引脚对应通道"
    )
    gnd_pin: Optional[str] = Field(
        None,
        description="GND引脚对应通道"
    )


# ============================================================
# 场景A：数字芯片参数模型
# ============================================================

class DigitalDCParam(BaseModel):
    """数字芯片 DC 测试参数"""
    param_name: str = Field(
        ...,
        description=(
            "参数名称，必须是STS8200S支持的DC参数: "
            "CONNECT/FUN/VIH/VIL/VOH/VOL/VIK/"
            "II/IIH/IIL/IOZH/IOZL/IOH/IOL/IOS/"
            "ICCH/ICCL/Ron/DeltaRon"
        )
    )
    category: Literal["DC"] = Field(
        default="DC",
        description="参数类型固定为DC"
    )
    test_pin: str = Field(
        default="",
        description="被测引脚名称, 如 Y0, A1, GND 等"
    )
    vcc_level: Optional[float] = Field(
        None,
        description="VCC供电电压(V), 如 5.0"
    )
    vih_level: Optional[float] = Field(
        None,
        description="输入高电平(V)"
    )
    vil_level: Optional[float] = Field(
        None,
        description="输入低电平(V)"
    )
    voh_level: Optional[float] = Field(
        None,
        description="输出高电平判断阈值(V)"
    )
    vol_level: Optional[float] = Field(
        None,
        description="输出低电平判断阈值(V)"
    )
    force_current: Optional[float] = Field(
        None,
        description="强制电流(A), 用于IOH/IOL测试"
    )
    min_val: Optional[float] = Field(None, description="最小值")
    typ_val: Optional[float] = Field(None, description="典型值")
    max_val: Optional[float] = Field(None, description="最大值")
    unit: str = Field(default="", description="单位: V/mV/mA/μA/Ω等")
    page: int = Field(default=0, description="Datasheet来源页码")
    confidence: float = Field(default=0.9, description="置信度0.0~1.0")


class DigitalACParam(BaseModel):
    """数字芯片 AC 测试参数"""
    param_name: str = Field(
        ...,
        description=(
            "参数名称，必须是STS8200S支持的AC参数: "
            "Tr(tTLH)/Tf(tTHL)/tPHL/tPLH"
        )
    )
    category: Literal["AC"] = Field(
        default="AC",
        description="参数类型固定为AC"
    )
    test_pin: str = Field(
        default="",
        description="被测引脚名称"
    )
    input_pin: str = Field(
        default="",
        description="触发输入引脚"
    )
    vcc_level: Optional[float] = Field(
        None,
        description="VCC供电电压(V)"
    )
    threshold_high: Optional[float] = Field(
        None,
        description="上升沿阈值电压(V), 通常为VCC的90%"
    )
    threshold_low: Optional[float] = Field(
        None,
        description="下降沿阈值电压(V), 通常为VCC的10%"
    )
    min_val: Optional[float] = Field(None, description="最小值")
    typ_val: Optional[float] = Field(None, description="典型值")
    max_val: Optional[float] = Field(None, description="最大值")
    unit: str = Field(default="ns", description="单位: ns/μs/ms")
    page: int = Field(default=0, description="Datasheet来源页码")
    confidence: float = Field(default=0.9, description="置信度0.0~1.0")


class DigitalTestPlan(BaseModel):
    """数字芯片完整测试计划"""
    chip_name: str = Field(default="", description="芯片型号")
    chip_family: str = Field(
        default="",
        description="芯片系列: 74系列/54系列/4000系列/存储器"
    )
    pin_count: int = Field(
        default=0,
        description="引脚总数, STS8200S支持≤24引脚"
    )
    vcc_nominal: Optional[float] = Field(
        None,
        description="标称VCC电压(V)"
    )
    vcc_min: Optional[float] = Field(None, description="VCC最小值(V)")
    vcc_max: Optional[float] = Field(None, description="VCC最大值(V)")
    dc_params: List[DigitalDCParam] = Field(
        default_factory=list,
        description="DC测试参数列表"
    )
    ac_params: List[DigitalACParam] = Field(
        default_factory=list,
        description="AC测试参数列表"
    )


# ============================================================
# 场景B：模拟芯片参数模型
# ============================================================

class LDOParam(BaseModel):
    """线性稳压器(LDO) 测试参数 - 对应L7805CV"""
    param_name: str = Field(
        ...,
        description=(
            "参数名称: "
            "VO(输出电压)/Sv(电压调整率)/Si(负载调整率)/Iq(静态电流)"
        )
    )
    category: Literal["LDO"] = Field(
        default="LDO",
        description="参数类型固定为LDO"
    )
    vin_min: Optional[float] = Field(
        None,
        description="输入电压最小值(V)"
    )
    vin_max: Optional[float] = Field(
        None,
        description="输入电压最大值(V)"
    )
    iout_min: Optional[float] = Field(
        None,
        description="输出电流最小值(A)"
    )
    iout_max: Optional[float] = Field(
        None,
        description="输出电流最大值(A)"
    )
    min_val: Optional[float] = Field(None, description="最小值")
    typ_val: Optional[float] = Field(None, description="典型值")
    max_val: Optional[float] = Field(None, description="最大值")
    unit: str = Field(default="", description="单位: V/mV/mA/μA/%/V等")
    vi_channel_in: Optional[str] = Field(
        None,
        description="输入端VI源通道, 如 FVI0"
    )
    vi_channel_out: Optional[str] = Field(
        None,
        description="输出端VI源通道(测量用), 如 FVI1"
    )
    page: int = Field(default=0, description="Datasheet来源页码")
    confidence: float = Field(default=0.9, description="置信度0.0~1.0")


class EEPROMParam(BaseModel):
    """EEPROM 测试参数 - 对应AT24C01"""
    param_name: str = Field(
        ...,
        description=(
            "参数名称: "
            "READ_55/WRITE_55/READ_AA/WRITE_AA/READ_DIFF/WRITE_DIFF"
        )
    )
    category: Literal["EEPROM"] = Field(
        default="EEPROM",
        description="参数类型固定为EEPROM"
    )
    test_data: str = Field(
        default="",
        description="测试数据模式: 55H/AAH/DIFF"
    )
    operation: Literal["READ", "WRITE", "READ_WRITE"] = Field(
        default="READ_WRITE",
        description="操作类型"
    )
    scl_channel: Optional[str] = Field(
        None,
        description="SCL时钟线对应DIO通道"
    )
    sda_channel: Optional[str] = Field(
        None,
        description="SDA数据线对应DIO通道"
    )
    vcc_level: Optional[float] = Field(
        None,
        description="VCC供电电压(V)"
    )
    min_val: Optional[float] = Field(None, description="最小值")
    typ_val: Optional[float] = Field(None, description="典型值")
    max_val: Optional[float] = Field(None, description="最大值")
    unit: str = Field(default="", description="单位")
    page: int = Field(default=0, description="Datasheet来源页码")
    confidence: float = Field(default=0.9, description="置信度0.0~1.0")


class AnalogMultiSiteTestPlan(BaseModel):
    """多工位模拟芯片测试计划"""
    chip_name: str = Field(default="", description="芯片型号")
    chip_type: Literal["LDO", "EEPROM", "UNKNOWN"] = Field(
        default="UNKNOWN",
        description="芯片类型"
    )
    ldo_params: List[LDOParam] = Field(
        default_factory=list,
        description="LDO测试参数列表"
    )
    eeprom_params: List[EEPROMParam] = Field(
        default_factory=list,
        description="EEPROM测试参数列表"
    )


# ============================================================
# 通用模型（向后兼容 + 场景C）
# ============================================================

class DCParam(BaseModel):
    """通用DC参数模型"""
    param_name: str = Field(..., description="参数名")
    category: str = Field(
        default="A",
        description="A=电气特性/B=绝对最大值/C=工作条件"
    )
    test_scenario: Literal[
        "DIGITAL_DC", "DIGITAL_AC", "LDO", "EEPROM", "GENERAL"
    ] = Field(
        default="GENERAL",
        description="测试场景标识"
    )
    condition: str = Field(default="", description="完整测试条件")
    min_val: Optional[float] = Field(None, description="最小值")
    typ_val: Optional[float] = Field(None, description="典型值")
    max_val: Optional[float] = Field(None, description="最大值")
    unit: str = Field(default="", description="单位")
    page: int = Field(default=0, description="来源页码")
    confidence: float = Field(default=0.9, description="置信度")
    sts_test_function: Optional[str] = Field(
        None,
        description=(
            "对应STS8200S测试函数名: "
            "FOVI_Test/DIO_Test/QTMU_Test/ACSM_Test等"
        )
    )
    sts_resource: Optional[STSResourceMapping] = Field(
        None,
        description="STS8200S硬件资源映射"
    )

    @model_validator(mode="after")
    def validate_sts_limits(self) -> "DCParam":
        """校验参数值是否超出STS8200S硬件量程"""
        return self


class TestPlan(BaseModel):
    """统一测试计划模型"""
    chip_name: str = Field(default="", description="芯片型号")
    chip_type: Literal[
        "DIGITAL_74", "DIGITAL_54", "DIGITAL_4000",
        "MEMORY", "LDO", "EEPROM", "ANALOG_GENERAL", "UNKNOWN"
    ] = Field(
        default="UNKNOWN",
        description="芯片类型"
    )
    # 通用DC参数
    dc_params: List[DCParam] = Field(
        default_factory=list,
        description="通用DC/AC参数列表"
    )
    # 场景A：数字芯片专用
    digital_plan: Optional[DigitalTestPlan] = Field(
        None,
        description="数字芯片专用测试计划"
    )
    # 场景B：模拟芯片专用
    analog_plan: Optional[AnalogMultiSiteTestPlan] = Field(
        None,
        description="模拟芯片专用测试计划"
    )
    # 新增：引脚定义列表
    pin_definitions: List[PinDefinition] = Field(
        default_factory=list,
        description="芯片引脚定义，从Datasheet引脚表自动提取"
    )


class RangeRecommendation(BaseModel):
    """AI 量程推荐建议"""
    param: str = Field(..., description="建议项名称")
    value: str = Field(..., description="推荐量程/值")
    reason: str = Field(..., description="推荐理由")
    priority: str = Field(default="normal", description="优先级: high/normal")


class RangeRecommendation(BaseModel):
    """AI 量程推荐建议"""
    param: str = Field(..., description="建议项名称")
    value: str = Field(..., description="推荐量程/值")
    reason: str = Field(..., description="推荐理由")
    priority: str = Field(default="normal", description="优先级: high/normal")


# ============================================================
# 结果模型
# ============================================================

class ExtractionResult(BaseModel):
    """提取结果模型"""
    status: str = Field(..., description="状态：success/error")
    chip_name: str = Field(default="", description="芯片型号")
    chip_type: str = Field(default="UNKNOWN", description="识别的芯片类型")
    test_scenario: str = Field(
        default="GENERAL",
        description="测试场景: DIGITAL/ANALOG_LDO/ANALOG_EEPROM/GENERAL"
    )
    total_params: int = Field(default=0, description="总参数数")
    a_params: int = Field(default=0, description="A类参数数")
    b_params: int = Field(default=0, description="B类参数数")
    c_params: int = Field(default=0, description="C类参数数")
    blocked_params: int = Field(default=0, description="被拦截参数数")
    dc_test_items: int = Field(default=0, description="DC测试项数量")
    ac_test_items: int = Field(default=0, description="AC测试项数量")
    ldo_test_items: int = Field(default=0, description="LDO测试项数量")
    eeprom_test_items: int = Field(default=0, description="EEPROM测试项数量")
    excel_path: Optional[str] = Field(None, description="Excel文件路径")
    json_path: Optional[str] = Field(None, description="JSON文件路径")
    errors: List[str] = Field(default_factory=list, description="错误列表")
    warnings: List[str] = Field(default_factory=list, description="警告列表")
    sts_compatibility: dict = Field(
        default_factory=dict,
        description="STS8200S硬件适配性检查报告"
    )
    # 新增：引脚定义
    pin_definitions: List[PinDefinition] = Field(
        default_factory=list,
        description="自动提取的引脚定义列表"
    )
    parameters: List[DCParam] = Field(
        default_factory=list,
        description="提取到的参数列表"
    )
    # 新增：量程推荐
    range_recommendations: List[RangeRecommendation] = Field(
        default_factory=list,
        description="AI自动生成的硬件量程推荐建议"
    )


class ValidationResult(BaseModel):
    """校验结果模型"""
    is_valid: bool = Field(..., description="是否通过校验")
    errors: List[str] = Field(default_factory=list, description="错误列表")
    warnings: List[str] = Field(
        default_factory=list,
        description="警告列表"
    )
    sts_warnings: List[str] = Field(
        default_factory=list,
        description="STS8200S硬件兼容性警告"
    )

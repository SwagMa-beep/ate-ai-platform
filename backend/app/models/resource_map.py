"""
资源映射数据模型 - 模块二
面向STS8200S三种适配器场景
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal


# ============================================================
# 适配器常量定义
# ============================================================

# 适配器型号
ADAPTER_MODELS = {
    "DIGITAL":  "Y.SH.8281-13",   # 数字芯片适配器
    "LDO":      "Y.SH.8281-4",    # 模拟LDO适配器
    "LDO_DUAL": "Y.SH.8281-10",   # 多工位LDO适配器
    "EEPROM":   "Y.SH.8281-4",    # EEPROM复用模拟适配器
}

# ── 适配器①BOM：Y.SH.8281-4（模拟LDO）──────────────────────
BOM_ANALOG_LDO = [
    {"位号": "C1,C3,C6", "数量": 3, "值": "0.1uF",       "封装": "0402", "说明": "去耦电容"},
    {"位号": "C2,C4,C7", "数量": 3, "值": "4.7uF",       "封装": "0805", "说明": "电源滤波电容"},
    {"位号": "C5",       "数量": 1, "值": "2nF",         "封装": "0402", "说明": "滤波电容"},
    {"位号": "C8,C9",    "数量": 2, "值": "2.2uF",       "封装": "0805", "说明": "输出滤波电容"},
    {"位号": "C10",      "数量": 1, "值": "1nF",         "封装": "0402", "说明": "高频滤波"},
    {"位号": "K1,K2,K3", "数量": 3, "值": "AGQ200A4H",   "封装": "SMD",  "说明": "松下SPST继电器"},
    {"位号": "R1",       "数量": 1, "值": "10KΩ",        "封装": "0402", "说明": "CBIT3上拉电阻"},
    {"位号": "R2,R3",    "数量": 2, "值": "0Ω",          "封装": "0402", "说明": "跳线电阻"},
    {"位号": "U1",       "数量": 1, "值": "IC-SOCKET-SOP8","封装": "SOP8","说明": "芯片插座"},
    {"位号": "U2",       "数量": 1, "值": "EL7156",       "封装": "SOT23","说明": "高性能管脚驱动器"},
    {"位号": "U3",       "数量": 1, "值": "BAV99",        "封装": "SOT23","说明": "高速开关二极管(ESD保护)"},
    {"位号": "X1",       "数量": 1, "值": "STS8200S_R",   "封装": "IDC",  "说明": "STS8200S右侧接口"},
    {"位号": "X2",       "数量": 1, "值": "STS8200S_L",   "封装": "IDC",  "说明": "STS8200S左侧接口"},
]

# ── 适配器②BOM：Y.SH.8281-10（多工位LDO）───────────────────
BOM_DUAL_LDO = [
    {"位号": "C1,C4",    "数量": 2, "值": "1uF",         "封装": "0805", "说明": "电源滤波电容"},
    {"位号": "K1",       "数量": 1, "值": "AGQ200A4H",   "封装": "SMD",  "说明": "工位1继电器"},
    {"位号": "K2",       "数量": 1, "值": "AGQ200A4H",   "封装": "SMD",  "说明": "工位2继电器"},
    {"位号": "U1",       "数量": 1, "值": "IC-SOCKET-ZIF14","封装": "ZIF14","说明": "工位1芯片插座"},
    {"位号": "U2",       "数量": 1, "值": "IC-SOCKET-ZIF14","封装": "ZIF14","说明": "工位2芯片插座"},
    {"位号": "X1",       "数量": 1, "值": "STS8200S_R",   "封装": "IDC",  "说明": "STS8200S右侧接口"},
    {"位号": "X2",       "数量": 1, "值": "STS8200S_L",   "封装": "IDC",  "说明": "STS8200S左侧接口"},
]

# ── 适配器③BOM：Y.SH.8281-13（数字芯片）────────────────────
BOM_DIGITAL = [
    {"位号": "C1,C3,C5,C7,C9", "数量": 5, "值": "0.1uF",    "封装": "0402", "说明": "去耦电容"},
    {"位号": "C2,C4,C6,C8",    "数量": 4, "值": "10uF",     "封装": "0805", "说明": "电源滤波电容"},
    {"位号": "K1,K2",          "数量": 2, "值": "AGQ200A4H","封装": "SMD",  "说明": "松下SPST继电器"},
    {"位号": "R1,R2,R3,R4",    "数量": 4, "值": "51Ω",      "封装": "0402", "说明": "BUF634串联匹配电阻"},
    {"位号": "R5,R6",          "数量": 2, "值": "1KΩ",      "封装": "0402", "说明": "终端下拉电阻"},
    {"位号": "U1",             "数量": 1, "值": "IC-SOCKET-ZIF14","封装": "ZIF14","说明": "14引脚锁紧座"},
    {"位号": "U2,U3",          "数量": 2, "值": "BUF634",   "封装": "DIP8", "说明": "250mA高速缓冲器"},
    {"位号": "X1",             "数量": 1, "值": "STS8200S_R","封装": "IDC",  "说明": "STS8200S右侧接口"},
    {"位号": "X2",             "数量": 1, "值": "STS8200S_L","封装": "IDC",  "说明": "STS8200S左侧接口"},
]

# ── STS8200S资源规格 ─────────────────────────────────────────
STS_FOVI_VOLTAGE_RANGES = ["±1V", "±2V", "±5V", "±10V", "±20V", "±40V"]
STS_FOVI_CURRENT_RANGES = ["±100μA", "±1mA", "±10mA", "±100mA", "±1A(脉冲)"]
STS_PMU_VOLTAGE_RANGES  = ["PMU_VRANG_1V","PMU_VRANG_2V","PMU_VRANG_5V",
                            "PMU_VRANG_10V","PMU_VRANG_20V","PMU_VRANG_50V"]
STS_PMU_CURRENT_RANGES  = ["PMU_IRANG_1UA","PMU_IRANG_10UA","PMU_IRANG_100UA",
                            "PMU_IRANG_1MA","PMU_IRANG_10MA","PMU_IRANG_100MA",
                            "PMU_IRANG_1A"]


# ============================================================
# 数据模型
# ============================================================

class PinInfo(BaseModel):
    """单个引脚信息"""
    pin_no: int               = Field(...,  description="引脚编号")
    pin_name: str             = Field(...,  description="引脚名称，如 VIN/VOUT/GND/A1/Y0")
    function: str             = Field("",   description="引脚功能描述")
    direction: Literal[
        "IN", "OUT", "PWR", "GND", "BIDIR", "NC"
    ]                         = Field("IN", description="引脚方向")
    voltage_max: Optional[float] = Field(None, description="最大电压(V)")
    current_max: Optional[float] = Field(None, description="最大电流(A)")
    notes: str                = Field("",   description="备注")


class ResourceMapping(BaseModel):
    """单条资源映射记录"""
    pin_no: int               = Field(...,  description="芯片引脚号")
    pin_name: str             = Field(...,  description="引脚名称")
    function: str             = Field("",   description="引脚功能")
    direction: str            = Field("",   description="IN/OUT/PWR/GND")
    # STS8200S资源
    sts_resource: str         = Field(...,  description="STS8200S资源，如FH0/DIO3/CBIT0")
    resource_type: Literal[
        "FH_SH", "DIO", "CBIT", "TMU", "VDD", "GND", "NC"
    ]                         = Field(...,  description="资源类型")
    channel_no: int           = Field(0,    description="通道编号")
    # 测试配置
    force_mode: str           = Field("",   description="力模式：ForceV/ForceI")
    measure_mode: str         = Field("",   description="测量模式：MeasureV/MeasureI")
    voltage_range: str        = Field("",   description="电压量程档")
    current_range: str        = Field("",   description="电流量程档")
    notes: str                = Field("",   description="备注说明")


class PGSConfig(BaseModel):
    """PGS填表编程配置 - 单个测试函数"""
    test_id: int              = Field(...,  description="测试序号")
    test_name: str            = Field(...,  description="测试项名称，如CON_N/FUN_T/VOH_T")
    function_type: Literal[
        "GlobalVariable", "FUNCTION", "FIMV_PMU",
        "FVMI_PMU", "INLEVEL", "SUPPLY"
    ]                         = Field(...,  description="PGS函数类型")
    # GlobalVariable专用
    vector_file: str          = Field("",   description="向量文件名(.vecdio)")
    all_group: str            = Field("",   description="AllGroup引脚列表")
    in_group: str             = Field("",   description="INGroup输入引脚")
    out_group: str            = Field("",   description="OutGroup输出引脚")
    # 通用电源配置
    vcc_value: Optional[float]   = Field(None, description="VCC电压值(V)")
    vcc_vrang: str               = Field("",   description="VCC电压量程档")
    vcc_irang: str               = Field("",   description="VCC电流量程档")
    # FUNCTION专用
    start_label: str             = Field("",   description="向量起始Label")
    stop_label: str              = Field("",   description="向量结束Label")
    vih: Optional[float]         = Field(None, description="输入高电平(V)")
    vil: Optional[float]         = Field(None, description="输入低电平(V)")
    voh: Optional[float]         = Field(None, description="输出高电平(V)")
    vol: Optional[float]         = Field(None, description="输出低电平(V)")
    # PMU专用
    select_group: str            = Field("",   description="SELECT_GROUP")
    test_pins: str               = Field("",   description="TEST_PINS")
    pmu_value: Optional[float]   = Field(None, description="PMU力源值")
    pmu_vrang: str               = Field("",   description="PMU电压量程")
    pmu_irang: str               = Field("",   description="PMU电流量程")
    limit_min: Optional[float]   = Field(None, description="测量下限")
    limit_max: Optional[float]   = Field(None, description="测量上限")
    limit_unit: str              = Field("",   description="限值单位")
    # SUPPLY专用
    select_vcc: str              = Field("",   description="SelectVCC1/VCC2")
    open_channel: str            = Field("",   description="DisConnect/Connect")
    open_pins_group: str         = Field("",   description="需断开引脚组")
    # INLEVEL专用
    start_voltage: Optional[float] = Field(None, description="扫描起始电压(V)")
    stop_voltage: Optional[float]  = Field(None, description="扫描终止电压(V)")
    test_type: str                 = Field("",   description="VIH或VIL")
    # 通用
    notes: str                   = Field("",   description="备注")


class PGSDetailCondition(BaseModel):
    """PGS详细条件 - 每个测试项逐行展开"""
    test_name: str            = Field(...,  description="测试项名称")
    param_name: str           = Field(...,  description="对应TestPlan参数名")
    condition_key: str        = Field(...,  description="条件键，如VCC_VALUE1")
    condition_value: str      = Field(...,  description="条件值，如5.0")
    condition_unit: str       = Field("",   description="单位")
    notes: str                = Field("",   description="说明")


class PinGroupConfig(BaseModel):
    """引脚分组配置 - GlobalVariable用"""
    chip_name: str            = Field(...,  description="芯片型号")
    pin_count: int            = Field(...,  description="引脚总数")
    all_group: List[str]      = Field(default_factory=list, description="所有引脚名列表")
    in_group: List[str]       = Field(default_factory=list, description="输入引脚列表")
    out_group: List[str]      = Field(default_factory=list, description="输出引脚列表")
    pwr_group: List[str]      = Field(default_factory=list, description="电源引脚列表")
    gnd_group: List[str]      = Field(default_factory=list, description="地引脚列表")
    vector_file: str          = Field("",   description="对应的向量文件名")


class AdapterInfo(BaseModel):
    """适配器硬件信息"""
    adapter_model: str        = Field(...,  description="适配器型号")
    chip_type: str            = Field(...,  description="适用芯片类型")
    socket_type: str          = Field(...,  description="芯片插座类型")
    max_pin_count: int        = Field(...,  description="最大引脚数")
    vi_channels: List[str]    = Field(default_factory=list, description="可用VI源通道")
    dio_channels: List[str]   = Field(default_factory=list, description="可用DIO通道")
    cbit_channels: List[str]  = Field(default_factory=list, description="可用CBIT通道")
    tmu_channels: List[str]   = Field(default_factory=list, description="可用TMU通道")
    bom_items: List[Dict]     = Field(default_factory=list, description="BOM清单")
    notes: str                = Field("",   description="使用说明")


class ResourceMapResult(BaseModel):
    """模块二完整输出结果"""
    status: str               = Field(...,  description="success/error")
    chip_name: str            = Field("",   description="芯片型号")
    chip_type: str            = Field("",   description="芯片类型")
    adapter_model: str        = Field("",   description="推荐适配器型号")
    # 资源映射
    resource_mappings: List[ResourceMapping] = Field(
        default_factory=list, description="资源映射列表"
    )
    # PGS配置
    pgs_configs: List[PGSConfig] = Field(
        default_factory=list, description="PGS填表配置列表"
    )
    pgs_detail_conditions: List[PGSDetailCondition] = Field(
        default_factory=list, description="PGS详细条件列表"
    )
    # 引脚分组
    pin_groups: Optional[PinGroupConfig] = Field(
        None, description="引脚分组配置"
    )
    # 适配器信息
    adapter_info: Optional[AdapterInfo] = Field(
        None, description="适配器硬件信息"
    )
    # 输出文件
    excel_path: Optional[str] = Field(None, description="资源映射Excel路径")
    svg_path: Optional[str]   = Field(None, description="SVG原理图路径")
    bom_path: Optional[str]   = Field(None, description="BOM清单Excel路径")
    md_path: Optional[str]    = Field(None, description="PGS配置指南Markdown路径")
    errors: List[str]         = Field(default_factory=list)
    warnings: List[str]       = Field(default_factory=list)
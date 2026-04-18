"""
数据校验服务 - 面向STS8200S测试平台
增加STS8200S硬件量程和场景专属校验规则
"""
import pandas as pd
from typing import List, Dict
from app.models.testplan import (
    ValidationResult,
    STS8200S_LIMITS,
    DIGITAL_DC_PARAMS, DIGITAL_AC_PARAMS,
    LDO_PARAMS, EEPROM_PARAMS
)
from app.utils.logger import setup_logger

logger = setup_logger()


class DataValidator:
    """数据校验器 - STS8200S专用"""

    def clean_and_validate(
        self,
        df: pd.DataFrame,
        chip_type: str = "UNKNOWN"
    ) -> pd.DataFrame:
        """
        清洗和校验数据

        Args:
            df: 原始参数DataFrame
            chip_type: 芯片类型，用于选择场景校验规则

        Returns:
            清洗后的DataFrame
        """
        # ← 加这一行
        df = df.copy()
        logger.info(
            f" 开始数据清洗 | 芯片类型: {chip_type} | 总数: {len(df)}"
        )

        original_count = len(df)

        # ── 基础清洗 ──────────────────────────────────────
        df = self._basic_clean(df)
        logger.info(f"  去重后: {original_count} → {len(df)} 条")

        # ── 初始化校验列 ───────────────────────────────────
        df["Status"] = "待复核"
        df["Validation_Error"] = ""
        df["STS_Warning"] = ""

        # ── 通用校验规则 ───────────────────────────────────
        df = self._apply_common_rules(df)

        # ── STS8200S硬件量程校验 ───────────────────────────
        df = self._apply_sts_hardware_rules(df)

        # ── 场景专属校验规则 ───────────────────────────────
        if chip_type in {"DIGITAL_74", "DIGITAL_54", "DIGITAL_4000", "MEMORY"}:
            df = self._apply_digital_rules(df)
        elif chip_type == "LDO":
            df = self._apply_ldo_rules(df)
        elif chip_type == "EEPROM":
            df = self._apply_eeprom_rules(df)

        # ── 统计输出 ───────────────────────────────────────
        self._log_statistics(df)

        return df.reset_index(drop=True)

    # ----------------------------------------------------------
    # 基础清洗
    # ----------------------------------------------------------

    def _basic_clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """基础数据清洗"""
        # ← 加这一行，确保操作的是独立副本
        df = df.copy()
        # 去重
        df = df.drop_duplicates(
            subset=["param_name", "condition", "category"],
            keep="first"
        )

        # 数值列转float
        for col in ["min_val", "typ_val", "max_val"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df["confidence"] = pd.to_numeric(
            df["confidence"], errors="coerce"
        ).fillna(0.85)

        # category规范化
        if "category" not in df.columns:
            df["category"] = "A"
        df["category"] = (
            df["category"].fillna("A").str.upper().str.strip()
        )
        df.loc[~df["category"].isin(["A", "B", "C"]), "category"] = "A"

        return df

    # ----------------------------------------------------------
    # 通用校验规则
    # ----------------------------------------------------------

    def _apply_common_rules(self, df: pd.DataFrame) -> pd.DataFrame:
        """通用校验规则（适用于所有芯片类型）"""

        # 规则1: Min > Max → 拦截
        mask1 = (
            df["min_val"].notna()
            & df["max_val"].notna()
            & (df["min_val"] > df["max_val"])
        )
        df.loc[mask1, "Status"] = "已拦截"
        df.loc[mask1, "Validation_Error"] += "下限大于上限; "
        if mask1.sum() > 0:
            logger.warning(f"  [规则1] {mask1.sum()} 条 Min>Max")

        # 规则2: 三个值全空 → 拦截
        mask2 = (
            df["min_val"].isna()
            & df["typ_val"].isna()
            & df["max_val"].isna()
        )
        df.loc[mask2, "Status"] = "已拦截"
        df.loc[mask2, "Validation_Error"] += "无任何数值; "
        if mask2.sum() > 0:
            logger.warning(f"  [规则2] {mask2.sum()} 条无数值")

        # 规则3: 热阻参数 → 拦截
        thermal_kw = [
            "θ", "theta", "ψ", "psi",
            "thermal resistance", "JA", "JC", "JB", "JT"
        ]
        for kw in thermal_kw:
            mask_t = df["param_name"].str.contains(
                kw, case=False, na=False
            )
            if mask_t.sum() > 0:
                df.loc[mask_t, "Status"] = "已拦截"
                df.loc[mask_t, "Validation_Error"] += f"热特性参数({kw}); "

        # 规则4: 置信度低 → 人工确认
        mask4 = df["confidence"] < settings_confidence_threshold(0.75)
        df.loc[
            mask4 & (df["Status"] == "待复核"), "Status"
        ] = "需人工确认"
        df.loc[mask4, "Validation_Error"] += "置信度低; "
        if mask4.sum() > 0:
            logger.warning(f"  [规则4] {mask4.sum()} 条置信度<0.75")

        # 规则5: A类参数Condition为空 → 人工确认
        mask5 = (
            (df["category"] == "A")
            & (df["condition"].fillna("").str.strip() == "")
            & (df["Status"] == "待复核")
        )
        df.loc[mask5, "Status"] = "需人工确认"
        df.loc[mask5, "Validation_Error"] += "A类参数缺少测试条件; "
        if mask5.sum() > 0:
            logger.warning(
                f"  [规则5] {mask5.sum()} 条A类参数缺少条件"
            )

        # 规则6: 单位缺失 → 人工确认
        mask6 = (
            df["unit"].fillna("").str.strip() == ""
        ) & (df["Status"] == "待复核")
        df.loc[mask6, "Status"] = "需人工确认"
        df.loc[mask6, "Validation_Error"] += "缺少单位; "

        return df

    # ----------------------------------------------------------
    # STS8200S 硬件量程校验
    # ----------------------------------------------------------

    def _apply_sts_hardware_rules(
        self, df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        STS8200S硬件量程和兼容性校验
        不拦截，但生成STS_Warning警告
        """
        # 检查电压超出VI源量程
        voltage_units = ["V", "mV"]
        for unit_str in voltage_units:
            mask_unit = df["unit"].fillna("").str.strip() == unit_str
            for col in ["max_val", "typ_val"]:
                if col in df.columns:
                    vals = df.loc[mask_unit, col].copy()
                    if unit_str == "mV":
                        vals = vals / 1000
                    over_range = vals > STS8200S_LIMITS["VI_voltage_max"]
                    idx = df.loc[mask_unit].index[over_range]
                    if len(idx) > 0:
                        df.loc[idx, "STS_Warning"] += (
                            f"电压超出VI源量程"
                            f"({STS8200S_LIMITS['VI_voltage_max']}V); "
                        )
                        logger.warning(
                            f"  [STS] {len(idx)} 条参数电压超出VI源量程"
                        )

        # 检查电流超出VI源量程
        current_units = ["A", "mA"]
        for unit_str in current_units:
            mask_unit = df["unit"].fillna("").str.strip() == unit_str
            for col in ["max_val", "typ_val"]:
                if col in df.columns:
                    vals = df.loc[mask_unit, col].copy()
                    if unit_str == "mA":
                        vals = vals / 1000
                    over_range = vals.abs() > STS8200S_LIMITS["VI_current_max"]
                    idx = df.loc[mask_unit].index[over_range]
                    if len(idx) > 0:
                        df.loc[idx, "STS_Warning"] += (
                            f"电流超出VI源量程"
                            f"({STS8200S_LIMITS['VI_current_max'] * 1000}mA); "
                        )

        # 检查DIO通道电压范围
        dio_over = df.apply(
            lambda row: self._check_dio_voltage(row), axis=1
        )
        df.loc[dio_over, "STS_Warning"] += "DIO通道电压超出范围; "

        return df

    def _check_dio_voltage(self, row: pd.Series) -> bool:
        """检查某行参数是否超出DIO通道电压范围"""
        if row.get("sts_test_function") == "DIO_Test":
            if row.get("unit") == "V":
                max_v = row.get("max_val")
                min_v = row.get("min_val")
                if max_v is not None and max_v > STS8200S_LIMITS["DIO_voltage_high"]:
                    return True
                if min_v is not None and min_v < STS8200S_LIMITS["DIO_voltage_low"]:
                    return True
        return False

    # ----------------------------------------------------------
    # 场景A：数字芯片专属校验
    # ----------------------------------------------------------

    def _apply_digital_rules(
        self, df: pd.DataFrame
    ) -> pd.DataFrame:
        """数字芯片专属校验规则"""

        # 规则D1: param_name不在白名单 → 警告
        all_digital_params = DIGITAL_DC_PARAMS | DIGITAL_AC_PARAMS
        mask_d1 = (
            ~df["param_name"].isin(all_digital_params)
            & (df["category"] == "A")
            & (df["Status"] == "待复核")
        )
        df.loc[mask_d1, "Status"] = "需人工确认"
        df.loc[mask_d1, "Validation_Error"] += (
            "非STS8200S标准数字测试参数，需确认是否支持; "
        )
        if mask_d1.sum() > 0:
            logger.warning(
                f"  [规则D1] {mask_d1.sum()} 条非标准数字参数"
            )

        # 规则D2: VIH必须 > VIL
        vih_rows = df[df["param_name"] == "VIH"]
        vil_rows = df[df["param_name"] == "VIL"]
        if not vih_rows.empty and not vil_rows.empty:
            vih_min = vih_rows["min_val"].min()
            vil_max = vil_rows["max_val"].max()
            if (vih_min is not None and vil_max is not None
                    and vih_min <= vil_max):
                logger.warning(
                    f"  [规则D2] VIH_min({vih_min}) ≤ VIL_max({vil_max})，"
                    f"逻辑电平不合法"
                )
                df.loc[
                    df["param_name"].isin(["VIH", "VIL"]),
                    "STS_Warning"
                ] += "VIH与VIL电平范围重叠，需检查; "

        # 规则D3: VOH必须 > VOL
        voh_rows = df[df["param_name"] == "VOH"]
        vol_rows = df[df["param_name"] == "VOL"]
        if not voh_rows.empty and not vol_rows.empty:
            voh_min = voh_rows["min_val"].min()
            vol_max = vol_rows["max_val"].max()
            if (voh_min is not None and vol_max is not None
                    and voh_min <= vol_max):
                logger.warning(
                    f"  [规则D3] VOH_min({voh_min}) ≤ VOL_max({vol_max})"
                )
                df.loc[
                    df["param_name"].isin(["VOH", "VOL"]),
                    "STS_Warning"
                ] += "VOH与VOL电平范围重叠，需检查; "

        # 规则D4: IOH通常为负值，IOL为正值
        ioh_rows = df[df["param_name"] == "IOH"]
        if not ioh_rows.empty:
            positive_ioh = ioh_rows[
                ioh_rows["typ_val"].fillna(0) > 0
            ]
            if not positive_ioh.empty:
                df.loc[positive_ioh.index, "STS_Warning"] += (
                    "IOH通常为负值(拉电流)，请确认符号; "
                )

        # 规则D5: AC参数单位应为时间单位
        ac_mask = df["param_name"].isin(DIGITAL_AC_PARAMS)
        wrong_unit_mask = ac_mask & ~df["unit"].isin(
            ["ns", "μs", "us", "ms", "ps"]
        )
        df.loc[wrong_unit_mask, "STS_Warning"] += (
            "AC参数单位应为时间单位(ns/μs/ms); "
        )

        # 规则D6: 引脚数超出STS8200S支持范围检查
        # 通过DIO通道数判断（最多24路DIO）
        if "test_pin" in df.columns:
            unique_pins = df["test_pin"].nunique()
            if unique_pins > 24:
                logger.warning(
                    f"  [规则D6] 检测到 {unique_pins} 个引脚，"
                    f"超出STS8200S的24路DIO限制"
                )
                df["STS_Warning"] += "引脚数可能超出STS8200S的24路DIO限制; "

        return df

    # ----------------------------------------------------------
    # 场景B1：LDO专属校验
    # ----------------------------------------------------------

    def _apply_ldo_rules(self, df: pd.DataFrame) -> pd.DataFrame:
        """LDO专属校验规则 (L7805CV)"""

        # 规则L1: VO必须存在
        has_vo = "VO" in df["param_name"].values
        if not has_vo:
            logger.warning("  [规则L1] 未提取到VO(输出电压)参数")

        # 规则L2: VO典型值合理性检查（正电压稳压器）
        vo_rows = df[df["param_name"] == "VO"]
        if not vo_rows.empty:
            vo_typ = vo_rows["typ_val"].iloc[0]
            if vo_typ is not None and vo_typ < 0:
                df.loc[vo_rows.index, "Validation_Error"] += (
                    "VO为负值，L7805应为正电压; "
                )
                df.loc[vo_rows.index, "Status"] = "需人工确认"

        # 规则L3: Sv(电压调整率)单位检查
        sv_rows = df[df["param_name"] == "Sv"]
        if not sv_rows.empty:
            valid_sv_units = {"mV", "V", "%", "%/V", "μV/V"}
            invalid_sv = sv_rows[
                ~sv_rows["unit"].isin(valid_sv_units)
            ]
            if not invalid_sv.empty:
                df.loc[invalid_sv.index, "STS_Warning"] += (
                    "Sv单位异常，预期为mV/%/mV/V等; "
                )

        # 规则L4: Si(负载调整率)单位检查
        si_rows = df[df["param_name"] == "Si"]
        if not si_rows.empty:
            valid_si_units = {"mV", "V", "%", "mV/A"}
            invalid_si = si_rows[
                ~si_rows["unit"].isin(valid_si_units)
            ]
            if not invalid_si.empty:
                df.loc[invalid_si.index, "STS_Warning"] += (
                    "Si单位异常，预期为mV/%等; "
                )

        # 规则L5: VIN必须大于VO(保证稳压器正常工作)
        vo_typ = None
        if not vo_rows.empty:
            vo_typ = vo_rows["typ_val"].iloc[0]

        # 从condition字段提取VIN进行检查
        if vo_typ is not None:
            for idx, row in df[df["param_name"].isin(LDO_PARAMS)].iterrows():
                condition = str(row.get("condition", ""))
                if "VIN" in condition.upper():
                    # 简单提取VIN值
                    import re
                    vin_match = re.search(
                        r'VIN\s*=\s*([\d.]+)', condition, re.IGNORECASE
                    )
                    if vin_match:
                        vin_val = float(vin_match.group(1))
                        if vin_val <= vo_typ:
                            df.loc[idx, "STS_Warning"] += (
                                f"VIN({vin_val}V) ≤ VO({vo_typ}V)，"
                                f"稳压器可能无法正常工作; "
                            )

        return df

    # ----------------------------------------------------------
    # 场景B2：EEPROM专属校验
    # ----------------------------------------------------------

    def _apply_eeprom_rules(self, df: pd.DataFrame) -> pd.DataFrame:
        """EEPROM专属校验规则 (AT24C01)"""

        # 规则E1: 检查VCC范围是否合理(AT24C01为1.8V-5.5V)
        vcc_rows = df[
            df["param_name"].str.upper().isin(["VCC", "VDD", "SUPPLY"])
        ]
        if not vcc_rows.empty:
            vcc_max = vcc_rows["max_val"].max()
            if vcc_max is not None and vcc_max > 5.5:
                df.loc[vcc_rows.index, "STS_Warning"] += (
                    "AT24C01 VCC最大值为5.5V，请确认; "
                )

        # 规则E2: I2C时序参数单位应为时间单位
        i2c_timing_params = {
            "fSCL", "tSU", "tHD", "tLOW", "tHIGH",
            "tAA", "tBUF", "tSP"
        }
        timing_rows = df[
            df["param_name"].isin(i2c_timing_params)
        ]
        if not timing_rows.empty:
            wrong_unit = timing_rows[
                ~timing_rows["unit"].isin(
                    ["ns", "μs", "us", "ms", "kHz", "MHz", "Hz"]
                )
            ]
            if not wrong_unit.empty:
                df.loc[wrong_unit.index, "STS_Warning"] += (
                    "I2C时序参数单位异常; "
                )

        # 规则E3: 输入电流通常为μA级，大电流需警告
        input_current_rows = df[
            df["param_name"].isin(["ILI", "ILO", "II"])
        ]
        if not input_current_rows.empty:
            for idx, row in input_current_rows.iterrows():
                if row.get("unit") == "mA":
                    max_v = row.get("max_val")
                    if max_v is not None and abs(max_v) > 1:
                        df.loc[idx, "STS_Warning"] += (
                            "EEPROM输入电流通常为μA级，请确认; "
                        )

        return df

    # ----------------------------------------------------------
    # 统计与汇总
    # ----------------------------------------------------------

    def _log_statistics(self, df: pd.DataFrame) -> None:
        """打印校验统计"""
        valid_count = len(df[df["Status"] == "待复核"])
        warning_count = len(df[df["Status"] == "需人工确认"])
        blocked_count = len(df[df["Status"] == "已拦截"])
        sts_warning_count = len(
            df[df["STS_Warning"].fillna("") != ""]
        )

        logger.info(f"  ✅ 有效(待复核): {valid_count}")
        logger.info(f"  ⚠️  需人工确认: {warning_count}")
        logger.info(f"  ❌ 已拦截: {blocked_count}")
        logger.info(f"   STS8200S兼容性警告: {sts_warning_count}")

    def get_validation_summary(
        self, df: pd.DataFrame
    ) -> ValidationResult:
        """获取校验摘要"""
        errors = df[
            df["Status"] == "已拦截"
        ]["Validation_Error"].tolist()

        warnings = df[
            df["Status"] == "需人工确认"
        ]["Validation_Error"].tolist()

        sts_warnings = df[
            df["STS_Warning"].fillna("") != ""
        ]["STS_Warning"].tolist()

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            sts_warnings=sts_warnings
        )

    def get_sts_compatibility_report(
        self, df: pd.DataFrame, chip_type: str
    ) -> Dict:
        """
        生成STS8200S硬件适配性报告

        Returns:
            适配性报告字典
        """
        report = {
            "chip_type": chip_type,
            "is_compatible": True,
            "issues": [],
            "recommendations": []
        }

        # 检查是否有超量程参数
        sts_warnings = df[
            df["STS_Warning"].fillna("") != ""
        ]
        if not sts_warnings.empty:
            report["issues"].append(
                f"存在 {len(sts_warnings)} 条STS8200S硬件兼容性警告"
            )

        # 场景推荐
        if chip_type in {"DIGITAL_74", "DIGITAL_54", "DIGITAL_4000"}:
            report["recommendations"].extend([
                "使用24引脚以内的DUT适配器",
                "确认VCC拨码位置(GND和VCC)",
                "DIO通道按表1-1插座管脚对应关系配置",
                "DC测试使用FOVI_Test函数",
                "功能测试需编写向量文件(.vecdio)"
            ])
        elif chip_type == "LDO":
            report["recommendations"].extend([
                "使用模拟芯片适配器",
                "FVI0作为VIN输入端",
                "FVI1作为VOUT测量端",
                "Iq测试使用QTMU_Test精密测量",
                "多工位测试时注意VI源分组(0-3组/4-7组共用低端)"
            ])
        elif chip_type == "EEPROM":
            report["recommendations"].extend([
                "使用模拟芯片适配器",
                "SCL/SDA连接DIO通道",
                "VCC由VI源提供",
                "读写测试需编写I2C时序向量文件"
            ])

        # 引脚数检查
        if chip_type in {
            "DIGITAL_74", "DIGITAL_54", "DIGITAL_4000", "MEMORY"
        }:
            if "test_pin" in df.columns:
                pin_count = df["test_pin"].nunique()
                if pin_count > 24:
                    report["is_compatible"] = False
                    report["issues"].append(
                        f"引脚数({pin_count})超出STS8200S的24路DIO限制"
                    )

        return report


    def get_range_recommendations(
        self, df: pd.DataFrame, chip_type: str
    ) -> list:
        """
        AI 量程推荐：根据提取的参数值自动推荐 STS8200S 板卡量程。

        Returns:
            list of {param, value, unit, range_module, range_value, reason}
        """
        recommendations = []

        # ── 量程规则库（基于 STS8200S 编程手册 FOVI/QTMU/DIO 规格）──
        RANGE_RULES = [
            # ── 高压参数 ──────────────────────────────────────────
            {
                "params": ["BVCEO", "BVCBO", "BVDSS", "BVGSS", "BVEBO", "BV"],
                "unit": "V", "threshold": 30,
                "range_module": "FOVI ±50V 量程",
                "range_value": "±50V",
                "reason": "击穿电压超过30V，需选用 FOVI 的高压量程（±50V），确保测试安全裕量"
            },
            # ── 精密小电流 ────────────────────────────────────────
            {
                "params": ["Iq", "IQ", "IB", "IGSS", "IGSS_off", "II", "IIN", "IOFF"],
                "unit": "μA", "threshold": 0,
                "range_module": "QTMU ±1mA / ±10mA 精密量程",
                "range_value": "±1mA",
                "reason": "静态/漏电流通常为 μA 级，需使用 QTMU 精密电流模块确保测量精度"
            },
            # ── 大输出电流 ────────────────────────────────────────
            {
                "params": ["IOUT", "IOH", "IOL", "IOS"],
                "unit": "mA", "threshold": 100,
                "range_module": "FOVI ±100mA / ±1A 量程",
                "range_value": "±100mA",
                "reason": "输出电流超过100mA，需选用 FOVI 大电流量程以避免过载"
            },
            # ── 电源电流 ──────────────────────────────────────────
            {
                "params": ["ICC", "IDD", "ISS", "ICCL", "ICCH"],
                "unit": "mA", "threshold": 50,
                "range_module": "FOVI 100mA 量程",
                "range_value": "100mA",
                "reason": "电源电流超过50mA，推荐 FOVI 100mA 量程（低于50mA可用 QTMU）"
            },
            # ── 标准数字电平 ──────────────────────────────────────
            {
                "params": ["VIH", "VIL", "VOH", "VOL", "VT", "VTH", "VIK"],
                "unit": "V", "threshold": 0,
                "range_module": "FOVI ±10V / DIO 标准量程",
                "range_value": "±10V",
                "reason": "数字逻辑电平参数使用 FOVI ±10V 量程（TTL/CMOS 兼容）或 DIO 直接测量"
            },
            # ── LDO 输入/输出电压 ─────────────────────────────────
            {
                "params": ["VO", "VIN", "VOUT"],
                "unit": "V", "threshold": 0,
                "range_module": "FOVI ±10V 量程",
                "range_value": "±10V",
                "reason": "LDO 输入/输出电压通常在 10V 以内，推荐 FOVI ±10V 量程"
            },
            # ── 时序参数 ──────────────────────────────────────────
            {
                "params": ["tPHL", "tPLH", "tTHL", "tTLH", "tSU", "tHD", "Tr", "Tf"],
                "unit": "ns", "threshold": 0,
                "range_module": "ACSM 时序捕获模块",
                "range_value": "1ns 分辨率",
                "reason": "交流时序参数需使用 ACSM 模块捕获跳变沿，DIO 直接计时"
            },
        ]

        # 遍历数据，匹配规则
        seen_params = set()
        for rule in RANGE_RULES:
            matched = df[df["param_name"].isin(rule["params"])]
            if matched.empty:
                continue

            for _, row in matched.iterrows():
                pname = row.get("param_name", "")
                if pname in seen_params:
                    continue

                unit = str(row.get("unit", "")).strip()
                val  = row.get("max_val") or row.get("typ_val") or row.get("min_val")

                # 单位不匹配则跳过
                if rule["unit"] not in ("", "*") and unit != rule["unit"]:
                    # 宽松匹配（μA 和 uA 等效）
                    if not (rule["unit"] == "μA" and unit in ("uA", "μA", "µA")):
                        continue

                # 阈值检查
                try:
                    numeric_val = float(val) if val is not None else 0
                except (ValueError, TypeError):
                    numeric_val = 0

                if numeric_val >= rule["threshold"] or rule["threshold"] == 0:
                    seen_params.add(pname)
                    recommendations.append({
                        "param":        pname,
                        "value":        f"{val} {unit}".strip() if val else "N/A",
                        "range_module": rule["range_module"],
                        "range_value":  rule["range_value"],
                        "reason":       rule["reason"],
                        "priority":     "high" if rule["threshold"] >= 30 else "normal",
                    })

        # 若无匹配规则则给通用建议
        if not recommendations:
            recommendations.append({
                "param":        "通用",
                "value":        "—",
                "range_module": "FOVI ±10V 量程",
                "range_value":  "±10V",
                "reason":       "未识别到特殊量程需求，推荐默认使用 FOVI ±10V 标准量程",
                "priority":     "normal",
            })

        logger.info(f" 量程推荐完成: {len(recommendations)} 条")
        return recommendations


def settings_confidence_threshold(default: float) -> float:
    """获取置信度阈值配置"""
    try:
        from app.core.config import get_settings
        return get_settings().CONFIDENCE_THRESHOLD
    except Exception:
        return default

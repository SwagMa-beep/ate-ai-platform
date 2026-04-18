"""
STS8200S 测试代码静态校验器 - 模块三
对 AI 生成的 C++ 测试代码进行预编译语义校验，
无需真实编译器，基于正则 + 规则引擎实现。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List


# ── STS8200S 合法 API 常量 ────────────────────────────────────────
VALID_FOVI_RANGES = {
    "FOVI_1V", "FOVI_2V", "FOVI_5V", "FOVI_10V",
    "FOVI_20V", "FOVI_50V",
    "FOVI_1mA", "FOVI_10mA", "FOVI_100mA", "FOVI_1A",
}
VALID_QTMU_RANGES = {
    "QTMU_1uA", "QTMU_10uA", "QTMU_100uA",
    "QTMU_1mA", "QTMU_10mA", "QTMU_100mA",
}
REQUIRED_HOOKS = [
    "HardWareCfg",
    "InitBeforeTestFlow",
]
REQUIRED_INCLUDES = ["stdafx.h"]
MAX_DIO_CHANNELS  = 24
MAX_FOVI_CHANNELS = 24

# ── 结果数据结构 ──────────────────────────────────────────────────

@dataclass
class ValidationIssue:
    level:   str   # "error" | "warning" | "info"
    rule:    str
    message: str
    line:    int = 0

@dataclass
class StaticAnalysisResult:
    passed:   bool
    score:    int                            # 0-100
    issues:   List[ValidationIssue] = field(default_factory=list)
    summary:  str = ""

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.level == "warning"]

    def to_dict(self) -> dict:
        return {
            "passed":   self.passed,
            "score":    self.score,
            "summary":  self.summary,
            "errors":   [{"rule": i.rule, "message": i.message, "line": i.line}
                         for i in self.errors],
            "warnings": [{"rule": i.rule, "message": i.message, "line": i.line}
                         for i in self.warnings],
            "infos":    [{"rule": i.rule, "message": i.message}
                         for i in self.issues if i.level == "info"],
        }


# ── 静态分析器 ────────────────────────────────────────────────────

class CodeValidator:
    """STS8200S C++ 测试代码静态分析器"""

    def validate(self, code: str) -> StaticAnalysisResult:
        issues: List[ValidationIssue] = []
        lines  = code.splitlines()

        # ── R1: 必要头文件 ────────────────────────────────────────
        for inc in REQUIRED_INCLUDES:
            if not any(inc in ln for ln in lines):
                issues.append(ValidationIssue(
                    level="error", rule="R1",
                    message=f"缺少必要头文件 #include \"{inc}\"",
                ))

        # ── R2: 必要回调函数 ──────────────────────────────────────
        for hook in REQUIRED_HOOKS:
            pattern = rf"DUT_API\s+\w+\s+{re.escape(hook)}\s*\("
            if not re.search(pattern, code):
                issues.append(ValidationIssue(
                    level="error", rule="R2",
                    message=f"缺少必要回调函数 DUT_API {hook}()",
                ))

        # ── R3: DIO 通道号合法性 ──────────────────────────────────
        for i, ln in enumerate(lines, 1):
            m = re.search(r'SetDIO\s*\(\s*(\d+)', ln)
            if m:
                ch = int(m.group(1))
                if ch > MAX_DIO_CHANNELS:
                    issues.append(ValidationIssue(
                        level="error", rule="R3", line=i,
                        message=f"DIO 通道号 {ch} 超出 STS8200S 最大值 {MAX_DIO_CHANNELS}",
                    ))

        # ── R4: FOVI 通道号合法性 ─────────────────────────────────
        for i, ln in enumerate(lines, 1):
            m = re.search(r'UserFOVI\s*\(\s*(\d+)', ln)
            if m:
                ch = int(m.group(1))
                if ch >= MAX_FOVI_CHANNELS:
                    issues.append(ValidationIssue(
                        level="warning", rule="R4", line=i,
                        message=f"FOVI 通道号 {ch} 较大，确认板卡配置（最大 {MAX_FOVI_CHANNELS-1}）",
                    ))

        # ── R5: FOVI 量程常量合法性 ───────────────────────────────
        for i, ln in enumerate(lines, 1):
            m = re.search(r'(FOVI_\w+)', ln)
            if m:
                token = m.group(1)
                # 允许 FOVI_xxx 开头但不在白名单的情况给警告
                if token not in VALID_FOVI_RANGES and not token.startswith("FOVI_V"):
                    issues.append(ValidationIssue(
                        level="warning", rule="R5", line=i,
                        message=f"未识别的 FOVI 量程常量 \"{token}\"，请核对编程手册",
                    ))
                    break  # 只报一次

        # ── R6: SetTestResult 调用检查 ────────────────────────────
        func_count = len(re.findall(r"DUT_API\s+int\s+\w+", code))
        result_count = len(re.findall(r"SetTestResult\s*\(", code))
        if func_count > 0 and result_count == 0:
            issues.append(ValidationIssue(
                level="error", rule="R6",
                message="检测到测试函数但未调用 SetTestResult()，测试结果将无法上报",
            ))
        elif result_count < func_count:
            issues.append(ValidationIssue(
                level="warning", rule="R6",
                message=f"测试函数 {func_count} 个，SetTestResult 调用 {result_count} 次，部分函数可能缺少结果上报",
            ))

        # ── R7: StsGetParam 调用检查 ──────────────────────────────
        param_count = len(re.findall(r"StsGetParam\s*\(", code))
        if func_count > 0 and param_count == 0:
            issues.append(ValidationIssue(
                level="warning", rule="R7",
                message="未找到 StsGetParam() 调用，测试参数限值可能未从 PGS 读取",
            ))

        # ── R8: TODO 残留检测 ─────────────────────────────────────
        todo_lines = [i+1 for i, ln in enumerate(lines) if "TODO" in ln]
        if todo_lines:
            issues.append(ValidationIssue(
                level="warning", rule="R8",
                message=f"存在 {len(todo_lines)} 处 TODO 待完善（行 {todo_lines[:3]}...）",
            ))

        # ── R9: 空函数体检测 ──────────────────────────────────────
        empty_func = re.findall(
            r"DUT_API\s+int\s+(\w+)\s*\([^)]*\)\s*\{\s*//[^\n]*\n\s*(?:CParam[^\n]*\n\s*)?(?://[^\n]*\n\s*)?param->SetTestResult[^\n]*\n\s*return\s+0;\s*\}",
            code
        )
        if empty_func:
            issues.append(ValidationIssue(
                level="info", rule="R9",
                message=f"函数 {empty_func[:3]} 为骨架实现，需填充真实测量逻辑",
            ))

        # ── 计算评分 ──────────────────────────────────────────────
        error_count   = sum(1 for i in issues if i.level == "error")
        warning_count = sum(1 for i in issues if i.level == "warning")
        score = max(0, 100 - error_count * 25 - warning_count * 8)
        passed = error_count == 0

        summary = (
            f"校验通过 ✅ 评分 {score}/100"
            if passed else
            f"发现 {error_count} 个错误、{warning_count} 个警告，评分 {score}/100"
        )

        return StaticAnalysisResult(
            passed=passed, score=score,
            issues=issues, summary=summary,
        )

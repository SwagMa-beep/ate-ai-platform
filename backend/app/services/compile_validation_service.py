"""
Compile-oriented validation service for generated STS8200S C++ code.
Uses local stub headers plus a system compiler for syntax-only checks.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


STDAFX_STUB = """#pragma once
#include <cmath>
#include <cstdint>
#include <string>
#include <vector>
using std::string;
using std::vector;

using HANDLE = void*;
using DWORD = unsigned long;
using LPVOID = void*;
using LPCTSTR = const char*;
using BYTE = unsigned char;
using BOOL = int;

#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif

#define APIENTRY
#define DUT_API extern "C"

enum
{
    FV = 1,
    FI = 2,
    FIMV = 3,
    FVMI = 4,
    RELAY_ON = 1,
    RELAY_OFF = 0,
    FOVI_10V = 10,
    FOVI_100MA = 100,
    FOVI_10MA = 11,
    FOVI_100UA = 12,
    VRNG_1V = 18,
    VRNG_2V = 19,
    VRNG_5V = 20,
    VRNG_10V = 21,
    VRNG_20V = 22,
    VRNG_50V = 23,
    PMU_VRANG_1V = 18,
    PMU_VRANG_2V = 19,
    PMU_VRANG_5V = 20,
    PMU_VRANG_10V = 21,
    PMU_VRANG_20V = 22,
    PMU_VRANG_50V = 23,
    IRNG_1UA = 30,
    IRNG_10UA = 31,
    IRNG_100UA = 32,
    IRNG_1MA = 33,
    IRNG_10MA = 34,
    IRNG_100MA = 35,
    IRNG_1A = 36,
    PMU_IRANG_1UA = 30,
    PMU_IRANG_10UA = 31,
    PMU_IRANG_100UA = 32,
    PMU_IRANG_1MA = 33,
    PMU_IRANG_10MA = 34,
    PMU_IRANG_100MA = 35,
    PMU_IRANG_1A = 36,
    MIRET = 40,
    AVERAGE_RESULT = 41,
};

inline void delay_us(int) {}
inline void delay_ms(int) {}
inline void STSSetHardwareCheck(int) {}
"""


USERCLASS_STUB = """#pragma once
#include "stdafx.h"

class CParam
{
public:
    void SetTestResult(int, int, double) {}
    void SetTestResult(int, int, int) {}
    void SetResultRemark(int, int, const char*) {}
};

inline CParam* StsGetParam(short, const char*)
{
    static CParam param;
    return &param;
}

class FOVI
{
public:
    template <typename... Args>
    FOVI(Args...) {}

    template <typename... Args>
    void Set(Args...) {}

    template <typename... Args>
    void MeasureVI(Args...) {}

    template <typename... Args>
    double GetMeasResult(Args...) { return 0.0; }
};

class UserPMU
{
public:
    template <typename... Args>
    UserPMU(Args...) {}

    template <typename... Args>
    double SetAndMeas(Args...) { return 0.0; }

    template <typename... Args>
    void Reset(Args...) {}
};

class UserDIO
{
public:
    template <typename... Args>
    UserDIO(Args...) {}

    template <typename... Args>
    void Connect(Args...) {}

    template <typename... Args>
    void Disconnect(Args...) {}

    template <typename... Args>
    void SetPinLevel(Args...) {}

    template <typename... Args>
    void Run(Args...) {}

    template <typename... Args>
    void SaveFailMap(Args...) {}

    template <typename... Args>
    void SetChannelVIH(Args...) {}

    template <typename... Args>
    void SetChannelVIL(Args...) {}

    template <typename... Args>
    void GetBoardFailCount(Args...) {}

    int GetPatternRunResult() { return 0; }
};

class CBIT128
{
public:
    template <typename... Args>
    CBIT128(Args...) {}
};

class QTMU_PLUS
{
public:
    template <typename... Args>
    QTMU_PLUS(Args...) {}

    template <typename... Args>
    void Init(Args...) {}
};

static UserPMU pmu;
static UserDIO dio(0, 1, 2);
static FOVI VL(0, "VL");
static FOVI VH(1, "VH");
static FOVI EN(2, "EN");
static FOVI VIN(3, "VIN");
static FOVI GND(4, "GND");
static FOVI VOUT(5, "VOUT");
"""


class CompileValidationService:
    """Syntax-only validation using locally available C++ compilers."""

    def __init__(self) -> None:
        self.compiler = shutil.which("g++") or shutil.which("clang++") or shutil.which("cl")

    def validate(self, code: str, filename: str = "generated_test.cpp") -> dict:
        if not self.compiler:
            return {
                "attempted": False,
                "passed": False,
                "compiler": None,
                "command": [],
                "diagnostics": ["No local C++ compiler found; compile validation skipped."],
            }

        with tempfile.TemporaryDirectory(prefix="ate_codegen_compile_") as temp_dir:
            temp_path = Path(temp_dir)
            source_path = temp_path / filename
            (temp_path / "stdafx.h").write_text(STDAFX_STUB, encoding="utf-8")
            (temp_path / "UserClass.h").write_text(USERCLASS_STUB, encoding="utf-8")
            source_path.write_text(code, encoding="utf-8")

            command = [self.compiler, "-std=c++17", "-fsyntax-only", str(source_path)]
            result = subprocess.run(
                command,
                cwd=temp_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            diagnostics = []
            if result.stdout.strip():
                diagnostics.extend(line for line in result.stdout.splitlines() if line.strip())
            if result.stderr.strip():
                diagnostics.extend(line for line in result.stderr.splitlines() if line.strip())

            return {
                "attempted": True,
                "passed": result.returncode == 0,
                "compiler": self.compiler,
                "command": command,
                "diagnostics": diagnostics[:40],
            }

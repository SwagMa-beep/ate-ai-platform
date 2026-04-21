from app.services.code_validator import CodeValidator


VALID_STS_CODE = """
#include "stdafx.h"
#include "UserClass.h"

DUT_API void HardWareCfg()
{
    STSSetHardwareCheck(FALSE);
}

DUT_API void InitBeforeTestFlow()
{
}

DUT_API int CON(short funcindex, LPCTSTR funclabel)
{
    CParam *CON = StsGetParam(funcindex, "CON");
    CON->SetTestResult(0, 0, 0.1);
    return 0;
}
"""


def test_validator_accepts_minimal_sts_code():
    result = CodeValidator().validate(VALID_STS_CODE)

    assert result.passed is True
    assert result.errors == []
    assert result.score == 100


def test_validator_rejects_missing_required_contracts():
    code = """
DUT_API int FUN(short funcindex, LPCTSTR funclabel)
{
    return 0;
}
"""

    result = CodeValidator().validate(code)

    assert result.passed is False
    assert {issue.rule for issue in result.errors} == {"R1", "R2", "R6"}


def test_validator_flags_out_of_range_dio_channel():
    code = VALID_STS_CODE.replace(
        "CON->SetTestResult(0, 0, 0.1);",
        "SetDIO(25, 3.3, OUT);\n    CON->SetTestResult(0, 0, 0.1);",
    )

    result = CodeValidator().validate(code)

    assert result.passed is False
    assert any(issue.rule == "R3" and issue.line > 0 for issue in result.errors)

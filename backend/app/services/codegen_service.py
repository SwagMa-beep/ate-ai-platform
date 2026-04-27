from __future__ import annotations

import textwrap
from typing import Optional

from openai import OpenAI

from app.core.config import get_settings
from app.services.enterprise_code_knowledge import get_enterprise_code_knowledge_service
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()

STS_API_REFERENCE = """
STS8200S programming constraints:
1. Include "stdafx.h" and "UserClass.h" when DIO/PMU wrappers are used.
2. Keep hook signatures stable: HardWareCfg / InitBeforeTestFlow / InitAfterTestFlow / SetupFailSite.
3. Each test function should call StsGetParam() and SetTestResult().
4. Prefer enterprise sample APIs and sequencing when available.
"""

PMU_ALIAS_BLOCK = textwrap.dedent("""
    // PMU range aliases keep generated code consistent across enterprise samples.
    #ifndef PMU_VRANG_1V
    #define PMU_VRANG_1V VRNG_1V
    #endif
    #ifndef PMU_VRANG_2V
    #define PMU_VRANG_2V VRNG_2V
    #endif
    #ifndef PMU_VRANG_5V
    #define PMU_VRANG_5V VRNG_5V
    #endif
    #ifndef PMU_VRANG_10V
    #define PMU_VRANG_10V VRNG_10V
    #endif
    #ifndef PMU_VRANG_20V
    #define PMU_VRANG_20V VRNG_20V
    #endif
    #ifndef PMU_VRANG_50V
    #define PMU_VRANG_50V VRNG_50V
    #endif
    #ifndef PMU_IRANG_1UA
    #define PMU_IRANG_1UA IRNG_1UA
    #endif
    #ifndef PMU_IRANG_10UA
    #define PMU_IRANG_10UA IRNG_10UA
    #endif
    #ifndef PMU_IRANG_100UA
    #define PMU_IRANG_100UA IRNG_100UA
    #endif
    #ifndef PMU_IRANG_1MA
    #define PMU_IRANG_1MA IRNG_1MA
    #endif
    #ifndef PMU_IRANG_10MA
    #define PMU_IRANG_10MA IRNG_10MA
    #endif
    #ifndef PMU_IRANG_100MA
    #define PMU_IRANG_100MA IRNG_100MA
    #endif
    #ifndef PMU_IRANG_1A
    #define PMU_IRANG_1A IRNG_1A
    #endif
""").strip()

PMU_RANGE_ALIASES = {
    "VRNG_1V": "PMU_VRANG_1V",
    "VRNG_2V": "PMU_VRANG_2V",
    "VRNG_5V": "PMU_VRANG_5V",
    "VRNG_10V": "PMU_VRANG_10V",
    "VRNG_20V": "PMU_VRANG_20V",
    "VRNG_50V": "PMU_VRANG_50V",
    "IRNG_1UA": "PMU_IRANG_1UA",
    "IRNG_10UA": "PMU_IRANG_10UA",
    "IRNG_100UA": "PMU_IRANG_100UA",
    "IRNG_1MA": "PMU_IRANG_1MA",
    "IRNG_10MA": "PMU_IRANG_10MA",
    "IRNG_100MA": "PMU_IRANG_100MA",
    "IRNG_1A": "PMU_IRANG_1A",
}

TEMPLATES: dict[str, str] = {
    "CON": textwrap.dedent("""
        DUT_API int CON(short funcindex, LPCTSTR funclabel)
        {
            CParam *CON = StsGetParam(funcindex, "CON");

            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            dio.Connect();
            dio.SetPinLevel(2.0, 0, 0, 0);
            delay_ms(5);
            dio.Run("T5", "T5");

            for (unsigned int i = 0; i < AllPin_Int.size(); i++)
            {
                Test_Value[i] = pmu.SetAndMeas(AllPin_Int[i], FIMV, -100e-6, VRNG_10V, IRNG_1MA);
                CON->SetTestResult(0, i, Test_Value[i]);
                CON->SetResultRemark(0, i, AllPin_String[i].c_str());
            }

            dio.Disconnect();
            pmu.Reset();
            delay_us(500);
            return 0;
        }
    """).strip(),
    "FUN": textwrap.dedent("""
        DUT_API int FUN(short funcindex, LPCTSTR funclabel)
        {
            CParam *FUN = StsGetParam(funcindex, "FUN");

            vcc1.Set(FV, {vcc}f, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            dio.Connect();
            dio.SetPinLevel(2.0, 0.7, 2.7, 0.5);
            delay_ms(5);
            dio.Run("T0", "T4");
            dio.SaveFailMap();

            int result = dio.GetPatternRunResult();
            FUN->SetTestResult(0, 0, result);

            dio.Disconnect();
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            return 0;
        }
    """).strip(),
    "VIH": textwrap.dedent("""
        DUT_API int VIH(short funcindex, LPCTSTR funclabel)
        {
            CParam *VIH = StsGetParam(funcindex, "VIH");
            int result = 0;
            double VIN = 0.0;

            vcc1.Set(FV, {vcc}f, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            dio.Connect();
            dio.SetPinLevel(4, 0, 3.4, 0.5);
            delay_ms(5);

            for (VIN = 0; VIN < {vcc}; VIN = VIN + 0.01)
            {
                dio.SetChannelVIH(0, 0, VIN);
                delay_us(500);
                dio.Run("T0", "T4");
                dio.GetBoardFailCount(0, result);
                if (result == 0)
                {
                    VIH->SetTestResult(0, 0, VIN);
                    VIH->SetResultRemark(0, 0, "A1");
                    break;
                }
            }

            dio.Disconnect();
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            return 0;
        }
    """).strip(),
    "VIL": textwrap.dedent("""
        DUT_API int VIL(short funcindex, LPCTSTR funclabel)
        {
            CParam *VIL = StsGetParam(funcindex, "VIL");
            int result = 0;
            double low = 0.0, high = {vcc}, epsilon = 0.001;

            vcc1.Set(FV, {vcc}f, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            dio.Connect();
            dio.SetPinLevel(4, 0, 3.4, 0.5);
            delay_ms(10);

            while (high - low > epsilon)
            {
                double mid = (low + high) / 2;
                dio.SetChannelVIL(0, 0, mid);
                delay_us(500);
                dio.Run("T0", "T4");
                dio.GetBoardFailCount(0, result);
                if (result != 0) high = mid;
                else low = mid;
            }
            VIL->SetTestResult(0, 0, high);
            VIL->SetResultRemark(0, 0, "A1");

            dio.Disconnect();
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            return 0;
        }
    """).strip(),
    "VOH": textwrap.dedent("""
        DUT_API int VOH(short funcindex, LPCTSTR funclabel)
        {
            CParam *VOH = StsGetParam(funcindex, "VOH");

            vcc1.Set(FV, {vcc_low}f, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            dio.Connect();
            dio.SetPinLevel(2.0, 0.7, 0, 0);
            delay_ms(5);
            dio.Run("T0", "T1");

            for (unsigned int i = 0; i < OutputPin_Int.size(); i++)
            {
                Test_Value[i] = pmu.SetAndMeas(OutputPin_Int[i], FIMV, -400e-6, VRNG_10V, IRNG_1MA);
                VOH->SetTestResult(0, i, Test_Value[i]);
                VOH->SetResultRemark(0, i, OutputPin_String[i].c_str());
            }

            pmu.Reset();
            dio.Disconnect();
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            return 0;
        }
    """).strip(),
    "VOL": textwrap.dedent("""
        DUT_API int VOL(short funcindex, LPCTSTR funclabel)
        {
            CParam *VOL1 = StsGetParam(funcindex, "VOL1");
            CParam *VOL2 = StsGetParam(funcindex, "VOL2");
            CParam* ParamArray[2] = { VOL1, VOL2 };
            vector<double> LoadCurrent = { 4e-3, 8e-3 };

            vcc1.Set(FV, {vcc_low}f, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            dio.Connect();
            dio.SetPinLevel(2.0, 0.8, 0, 0);
            delay_ms(5);
            dio.Run("T2", "T2");

            for (unsigned int i = 0; i < LoadCurrent.size(); i++)
                for (unsigned int j = 0; j < OutputPin_Int.size(); j++)
                {
                    Test_Value[j] = pmu.SetAndMeas(OutputPin_Int[j], FIMV, LoadCurrent[i], VRNG_10V, IRNG_10MA);
                    ParamArray[i]->SetTestResult(0, j, Test_Value[j]);
                    ParamArray[i]->SetResultRemark(0, j, OutputPin_String[j].c_str());
                }

            pmu.Reset();
            dio.Disconnect();
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            return 0;
        }
    """).strip(),
    "IOS": textwrap.dedent("""
        DUT_API int IOS(short funcindex, LPCTSTR funclabel)
        {
            CParam *IOS = StsGetParam(funcindex, "IOS");

            vcc1.Set(FV, {vcc_high}f, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            dio.Connect();
            dio.SetPinLevel(2.0, 0.7, 0, 0);
            delay_ms(5);
            dio.Run("T0", "T1");

            for (unsigned int i = 0; i < OutputPin_Int.size(); i++)
            {
                Test_Value[i] = pmu.SetAndMeas(OutputPin_Int[i], FVMI, 0.0, VRNG_10V, IRNG_100MA);
                IOS->SetTestResult(0, i, Test_Value[i] * 1e3);
                IOS->SetResultRemark(0, i, OutputPin_String[i].c_str());
            }

            pmu.Reset();
            dio.Disconnect();
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            return 0;
        }
    """).strip(),
    "ICC": textwrap.dedent("""
        DUT_API int ICC(short funcindex, LPCTSTR funclabel)
        {
            CParam *ICCH = StsGetParam(funcindex, "ICCH");
            CParam *ICCL = StsGetParam(funcindex, "ICCL");

            vcc1.Set(FV, {vcc_high}f, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            dio.Connect();
            dio.SetPinLevel({vcc_high}, 0, 0, 0);
            delay_ms(5);
            dio.Run("T0", "T1");

            vcc1.Set(FV, {vcc_high}f, FOVI_10V, FOVI_10MA, RELAY_ON);
            delay_us(500);
            vcc1.MeasureVI(10, 10);
            Test_Value[0] = vcc1.GetMeasResult(0, MIRET, AVERAGE_RESULT);
            ICCH->SetTestResult(0, 0, Test_Value[0] * 1e3);
            ICCH->SetResultRemark(0, 0, "ICCH");

            vcc1.Set(FV, 0.0, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            vcc1.Set(FV, {vcc_high}f, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            dio.Run("T0", "T2");
            vcc1.Set(FV, {vcc_high}f, FOVI_10V, FOVI_10MA, RELAY_ON);
            delay_us(500);
            vcc1.MeasureVI(10, 10);
            Test_Value[1] = vcc1.GetMeasResult(0, MIRET, AVERAGE_RESULT);
            ICCL->SetTestResult(0, 0, Test_Value[1] * 1e3);
            ICCL->SetResultRemark(0, 0, "ICCL");

            dio.Disconnect();
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);
            delay_us(500);
            return 0;
        }
    """).strip(),
    "LDO_DROPOUT": textwrap.dedent("""
        DUT_API int LDO_DROPOUT(short funcindex, LPCTSTR funclabel)
        {
            CParam *DROPOUT = StsGetParam(funcindex, "DROPOUT");
            double vin_step = 0.05;
            double vin = {vcc};
            double vout_nom = {vout};
            double dropout_v = 0.0;

            pmu.SetAndMeas({ldo_out_pin}, FIMV, -{load_ma}e-3, VRNG_10V, IRNG_1MA);
            delay_ms(5);

            for (vin = {vcc}; vin > 0.5; vin -= vin_step)
            {
                vcc1.Set(FV, (float)vin, FOVI_10V, FOVI_100MA, RELAY_ON);
                delay_ms(10);
                double measured_vout = pmu.SetAndMeas({ldo_out_pin}, FIMV, -{load_ma}e-3, VRNG_10V, IRNG_1MA);
                if (measured_vout < vout_nom * 0.99)
                {
                    dropout_v = vin - measured_vout;
                    break;
                }
            }
            DROPOUT->SetTestResult(0, 0, dropout_v);
            DROPOUT->SetResultRemark(0, 0, "VIN-VOUT");
            pmu.Reset();
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);
            return 0;
        }
    """).strip(),
    "LDO_ACCURACY": textwrap.dedent("""
        DUT_API int LDO_ACCURACY(short funcindex, LPCTSTR funclabel)
        {
            CParam *ACCURACY = StsGetParam(funcindex, "ACCURACY");
            vcc1.Set(FV, {vcc}f, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_ms(10);

            double measured_vout = pmu.SetAndMeas({ldo_out_pin}, FIMV, -1e-6, VRNG_10V, IRNG_100UA);
            double error_pct = (measured_vout - {vout}) / {vout} * 100.0;
            ACCURACY->SetTestResult(0, 0, error_pct);
            ACCURACY->SetResultRemark(0, 0, "VOUT_ERR%");

            pmu.Reset();
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);
            return 0;
        }
    """).strip(),
    "LDO_IQ": textwrap.dedent("""
        DUT_API int LDO_IQ(short funcindex, LPCTSTR funclabel)
        {
            CParam *IQ = StsGetParam(funcindex, "IQ");
            vcc1.Set(FV, {vcc}f, FOVI_10V, FOVI_10MA, RELAY_ON);
            delay_ms(10);

            vcc1.MeasureVI(10, 10);
            double iq = vcc1.GetMeasResult(0, MIRET, AVERAGE_RESULT);
            IQ->SetTestResult(0, 0, iq * 1e6);
            IQ->SetResultRemark(0, 0, "IQ_uA");

            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);
            return 0;
        }
    """).strip(),
}


def _build_file_header(chip_name: str, chip_type: str, test_items: list[str], user_prompt: str) -> str:
    return textwrap.dedent(f"""
        /******************************************************************************
        * STS8200S Test Program - AI generated with enterprise knowledge
        *
        * Chip Name: {chip_name}
        * Chip Type: {chip_type}
        * Test Items: {', '.join(test_items)}
        * User Prompt: {user_prompt}
        *
        * Review hardware mapping, limits, and vector labels before production use.
        ******************************************************************************/ 
        #include "stdafx.h"
        #include "UserClass.h"
        #include <vector>
        using namespace std;

        {PMU_ALIAS_BLOCK}
    """).strip()


def _build_pin_declarations(pin_names: list[str], input_pins: list[str], output_pins: list[str]) -> str:
    all_str = ", ".join(f'"{p}"' for p in pin_names)
    in_str = ", ".join(f'"{p}"' for p in input_pins)
    out_str = ", ".join(f'"{p}"' for p in output_pins)
    all_int = ", ".join(str(i) for i in range(len(pin_names)))
    in_int = ", ".join(str(i) for i, p in enumerate(pin_names) if p in input_pins)
    out_int = ", ".join(str(i) for i, p in enumerate(pin_names) if p in output_pins)
    return textwrap.dedent(f"""
        vector<string> AllPin_String = {{ {all_str} }};
        vector<string> InputPin_String = {{ {in_str} }};
        vector<string> OutputPin_String = {{ {out_str} }};

        vector<int> AllPin_Int = {{ {all_int} }};
        vector<int> InputPin_Int = {{ {in_int} }};
        vector<int> OutputPin_Int = {{ {out_int} }};
    """).strip()


def _build_default_callbacks(vcc: float) -> str:
    return textwrap.dedent(f"""
        DUT_API void HardWareCfg()
        {{
            STSSetHardwareCheck(FALSE);
        }}

        DUT_API void InitBeforeTestFlow()
        {{
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_ms(10);
            vcc1.Set(FV, {vcc}f, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
        }}

        DUT_API void InitAfterTestFlow()
        {{
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);
            delay_us(100);
        }}

        DUT_API void SetupFailSite(const unsigned char* byFailSite)
        {{
        }}
    """).strip()


def _normalize_pin_groups(
    pin_names: Optional[list[str]],
    input_pins: Optional[list[str]],
    output_pins: Optional[list[str]],
) -> tuple[list[str], list[str], list[str]]:
    if pin_names is None:
        pin_names = ["A1", "B1", "Y1", "A2", "B2", "Y2"]
    if input_pins is None:
        input_pins = ["A1", "B1", "A2", "B2"]
    if output_pins is None:
        output_pins = ["Y1", "Y2"]

    normalized_pin_names = [str(p) for p in pin_names if str(p).strip()]
    normalized_inputs = [str(p) for p in input_pins if str(p).strip() and str(p) in normalized_pin_names]
    normalized_outputs = [str(p) for p in output_pins if str(p).strip() and str(p) in normalized_pin_names]
    return normalized_pin_names, normalized_inputs, normalized_outputs


def _build_enterprise_digital_scaffold(pin_names: list[str], input_pins: list[str], output_pins: list[str]) -> str:
    return "\n".join([
        'FOVI vcc1(8, "vcc1");',
        'FOVI vcc2(9, "vcc2");',
        "CBIT128 cbit;",
        "QTMU_PLUS tmu0(0);",
        "",
        "double Test_Value[24] = { 0.0 };",
        "",
        _build_pin_declarations(pin_names, input_pins, output_pins),
        "",
        textwrap.dedent("""
            DUT_API void HardWareCfg()
            {
                STSSetHardwareCheck(FALSE);
            }

            DUT_API void InitBeforeTestFlow()
            {
                tmu0.Init();
                delay_us(100);

                vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
                vcc2.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
                delay_us(100);
            }

            DUT_API void InitAfterTestFlow()
            {
                vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);
                vcc2.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);
                delay_us(100);
            }

            DUT_API void SetupFailSite(const unsigned char* byFailSite)
            {
            }
        """).strip(),
    ]).strip()


def _build_enterprise_analog_scaffold() -> str:
    return textwrap.dedent("""
        FOVI EN(11, "EN");
        FOVI VIN(9, "VIN");
        FOVI GND(12, "GND");
        FOVI VOUT(8, "VOUT");
        FOVI VL(13, "VL");
        FOVI VH(14, "VH");

        CBIT128 cbit;
        QTMU_PLUS tmu0(0);

        BYTE K0 = 0;
        BYTE K1 = 1;
        BYTE K2 = 2;
        BYTE K3 = 3;

        DUT_API void HardWareCfg()
        {
            STSSetHardwareCheck(FALSE);
        }

        DUT_API void InitBeforeTestFlow()
        {
            tmu0.Init();

            VL.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            VH.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);

            EN.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            VIN.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            GND.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            VOUT.Set(FI, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_ms(5);
        }

        DUT_API void InitAfterTestFlow()
        {
            VL.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);
            VH.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);

            EN.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);
            VIN.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);
            GND.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);
            VOUT.Set(FI, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);
            delay_ms(5);
        }

        DUT_API void SetupFailSite(const unsigned char* byFailSite)
        {
        }
    """).strip()


def _build_stub_from_knowledge(item: str, description: str, apis: list[str]) -> str:
    api_hint = ", ".join(apis[:6]) if apis else "StsGetParam, SetTestResult"
    return textwrap.dedent(f"""
        DUT_API int {item}(short funcindex, LPCTSTR funclabel)
        {{
            CParam *param = StsGetParam(funcindex, "{item}");
            // Enterprise knowledge: {description}
            // Suggested APIs: {api_hint}
            param->SetTestResult(0, 0, 0);
            return 0;
        }}
    """).strip()


def _render_template(template: str, params: dict) -> str:
    rendered = template
    for key, value in params.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered


def _normalize_pmu_constants(code: str) -> str:
    normalized = code
    for old_token, new_token in sorted(PMU_RANGE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        normalized = normalized.replace(old_token, new_token)
    return normalized


class CodegenService:
    """Template assembly + enterprise code knowledge + optional RAG enhancement."""

    def __init__(self) -> None:
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> Optional[OpenAI]:
        if self._client is None and settings.DEEPSEEK_API_KEY:
            self._client = OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
            )
        return self._client

    def generate(
        self,
        chip_name: str,
        chip_type: str,
        test_items: list[str],
        user_prompt: str,
        pin_names: list[str] = None,
        input_pins: list[str] = None,
        output_pins: list[str] = None,
        vcc: float = 5.0,
        vout: float = 3.3,
        ldo_out_pin: int = 2,
        load_ma: float = 100.0,
    ) -> dict:
        knowledge = get_enterprise_code_knowledge_service()
        scenario = knowledge.resolve_scenario(chip_type)
        recommended_items = knowledge.recommend_test_items(chip_type)
        if not test_items:
            test_items = list(recommended_items)

        pin_names, input_pins, output_pins = _normalize_pin_groups(pin_names, input_pins, output_pins)
        vcc_low = round(vcc - 0.25, 2)
        vcc_high = round(vcc + 0.25, 2)
        fmt_params = {
            "vcc": vcc,
            "vcc_low": vcc_low,
            "vcc_high": vcc_high,
            "vout": vout,
            "ldo_out_pin": ldo_out_pin,
            "load_ma": load_ma,
        }

        if scenario == "digital":
            scaffold = _build_enterprise_digital_scaffold(pin_names, input_pins, output_pins)
        elif scenario == "analog":
            scaffold = _build_enterprise_analog_scaffold()
        else:
            scaffold = "\n\n".join([
                'FOVI vcc1(8, "vcc1");',
                "UserPMU pmu;",
                "UserDIO dio(0, 1, 2);",
                "double Test_Value[24] = { 0.0 };",
                _build_pin_declarations(pin_names, input_pins, output_pins),
                _build_default_callbacks(vcc),
            ])

        knowledge_items = []
        sections = [_build_file_header(chip_name, chip_type, test_items, user_prompt), "", scaffold, ""]
        for item in test_items:
            entry = knowledge.get_item_knowledge(item)
            if entry:
                knowledge_items.append({
                    "item": item,
                    "description": entry["description"],
                    "apis": entry["apis"],
                    "scenarios": entry["scenarios"],
                })

            code = TEMPLATES.get(item, "")
            if code:
                code = _render_template(code, fmt_params)
            else:
                enterprise_code = knowledge.get_sample_code(item)
                if enterprise_code:
                    code = enterprise_code
                else:
                    code = _build_stub_from_knowledge(
                        item=item,
                        description=entry["description"] if entry else f"Generated placeholder for {item}",
                        apis=entry["apis"] if entry else [],
                    )
            sections.append(code)
            sections.append("")

        skeleton_code = _normalize_pmu_constants("\n".join(sections))
        final_code = skeleton_code
        ai_analysis: list[str] = []
        retrieved_chunks: list[dict] = []
        knowledge_sections = knowledge.get_reference_sections(test_items, chip_type)

        if self.client and user_prompt.strip():
            rag_used = False
            try:
                from app.services.rag_service import get_rag_service

                rag_svc = get_rag_service()
                if rag_svc.is_ready:
                    rag_code, retrieved_chunks = rag_svc.generate_with_rag(
                        user_query=user_prompt,
                        chip_name=chip_name,
                        chip_type=chip_type,
                        skeleton_code=skeleton_code,
                        extra_context=(
                            f"Chip params: VCC={vcc}V, VOUT={vout}V\n\n"
                            + "\n\n".join(
                                f"[{section['title']}]\n{section['content']}"
                                for section in knowledge_sections[:6]
                            )
                        ),
                    )
                    if rag_code and len(rag_code) > 100:
                        final_code = _normalize_pmu_constants(rag_code)
                        rag_used = True
            except Exception as exc:
                logger.warning(f"RAG enhancement failed, keep enterprise skeleton: {exc}")

            if not rag_used:
                try:
                    final_code, ai_analysis = self._ai_polish(
                        skeleton=skeleton_code,
                        chip_name=chip_name,
                        chip_type=chip_type,
                        test_items=test_items,
                        user_prompt=user_prompt,
                        params=fmt_params,
                    )
                except Exception as exc:
                    logger.warning(f"AI polish failed, keep enterprise skeleton: {exc}")

        final_code = _normalize_pmu_constants(final_code)
        lines = final_code.splitlines()
        return {
            "code": final_code,
            "filename": f"{chip_name.replace(' ', '_')}_test.cpp",
            "lines": len(lines),
            "functions": len([line for line in lines if "DUT_API int" in line]),
            "chip_name": chip_name,
            "chip_type": chip_type,
            "test_items": test_items,
            "recommended_items": recommended_items,
            "knowledge_used": bool(knowledge_items),
            "knowledge_items": knowledge_items,
            "ai_analysis": ai_analysis,
            "retrieved_chunks": retrieved_chunks,
        }

    def _ai_polish(
        self,
        skeleton: str,
        chip_name: str,
        chip_type: str,
        test_items: list[str],
        user_prompt: str,
        params: dict,
    ) -> tuple[str, list[str]]:
        system_prompt = f"""You are a senior STS8200S ATE engineer.
{STS_API_REFERENCE}
Keep code structure intact. Improve comments and point out risks with // [WARNING]. Return only C++ code."""
        user_msg = f"""Chip: {chip_name} ({chip_type})
Tests: {", ".join(test_items)}
User prompt: {user_prompt}
Params: VCC={params['vcc']}V

Please improve this C++ code with concise professional comments:

{skeleton}
"""

        resp = self.client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=settings.MAX_TOKENS,
            temperature=0.2,
        )
        polished = (resp.choices[0].message.content or "").strip()
        if polished.startswith("```"):
            polished = "\n".join(line for line in polished.splitlines() if not line.startswith("```"))
        warnings = [
            line.strip().lstrip("/").strip()
            for line in polished.splitlines()
            if "[WARNING]" in line
        ]
        return polished or skeleton, warnings

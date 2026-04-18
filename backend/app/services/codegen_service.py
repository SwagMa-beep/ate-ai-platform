"""
模块三：测试代码生成服务
策略：模板生成骨架 + DeepSeek AI 润色注释与补全细节
"""
from __future__ import annotations
import textwrap
from typing import Optional
from openai import OpenAI
from app.core.config import get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()

# ─── STS8200S API 参考（注入 AI Prompt）──────────────────────
STS_API_REFERENCE = """
STS8200S C++ 编程规范（必须严格遵守）：
1. 包含头文件：#include "stdafx.h" 和 #include "UserClass.h"
2. 全局资源声明（根据实际通道）：
   FOVI vcc1(8, "vcc1");   // 电源通道8
   UserPMU pmu;
   UserDIO dio(0, 1, 2);   // DIO板卡0,1,2
3. 必须实现四个回调：
   DUT_API void HardWareCfg() { STSSetHardwareCheck(FALSE); }
   DUT_API void InitBeforeTestFlow() { ... }
   DUT_API void InitAfterTestFlow() { ... }
   DUT_API void SetupFailSite(const unsigned char* byFailSite) {}
4. 测试函数签名固定格式：
   DUT_API int FUNCNAME(short funcindex, LPCTSTR funclabel) { ... return 0; }
5. 获取参数对象：CParam *PARAM = StsGetParam(funcindex, "PARAM_NAME");
6. 记录结果：param->SetTestResult(site, index, value);
             param->SetResultRemark(site, index, "pin_name");
7. 电源API：vcc1.Set(FV, voltage, FOVI_10V, FOVI_100MA, RELAY_ON/OFF);
8. PMU测量：pmu.SetAndMeas(pinNum, FIMV/FVMI, value, VRNG_10V, IRNG_1MA);
9. DIO操作：dio.Connect(); dio.SetPinLevel(VIH,VIL,VOH,VOL); dio.Run("T0","T4");
10. 延时：delay_us(微秒); delay_ms(毫秒);
"""

# ─── 测试项模板库 ─────────────────────────────────────────────
TEMPLATES: dict[str, str] = {
    "CON": textwrap.dedent("""
        DUT_API int CON(short funcindex, LPCTSTR funclabel)
        {{
            CParam *CON = StsGetParam(funcindex, "CON");

            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            dio.Connect();
            dio.SetPinLevel(2.0, 0, 0, 0);
            delay_ms(5);
            dio.Run("T5", "T5");

            for (unsigned int i = 0; i < AllPin_Int.size(); i++)
            {{
                Test_Value[i] = pmu.SetAndMeas(AllPin_Int[i], FIMV, -100e-6, VRNG_10V, IRNG_1MA);
                CON->SetTestResult(0, i, Test_Value[i]);
                CON->SetResultRemark(0, i, AllPin_String[i].c_str());
            }}

            dio.Disconnect();
            pmu.Reset();
            delay_us(500);
            return 0;
        }}
    """),

    "FUN": textwrap.dedent("""
        DUT_API int FUN(short funcindex, LPCTSTR funclabel)
        {{
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
        }}
    """),

    "VIH": textwrap.dedent("""
        DUT_API int VIH(short funcindex, LPCTSTR funclabel)
        {{
            CParam *VIH = StsGetParam(funcindex, "VIH");
            int result;
            double VIN = 0.0;

            vcc1.Set(FV, {vcc}f, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            dio.Connect();
            dio.SetPinLevel(4, 0, 3.4, 0.5);
            delay_ms(5);

            for (VIN = 0; VIN < {vcc}; VIN = VIN + 0.01)
            {{
                dio.SetChannelVIH(0, 0, VIN);
                delay_us(500);
                dio.Run("T0", "T4");
                dio.GetBoardFailCount(0, result);
                if (result == 0)
                {{
                    VIH->SetTestResult(0, 0, VIN);
                    VIH->SetResultRemark(0, 0, "A1");
                    break;
                }}
            }}

            dio.Disconnect();
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            return 0;
        }}
    """),

    "VIL": textwrap.dedent("""
        DUT_API int VIL(short funcindex, LPCTSTR funclabel)
        {{
            CParam *VIL = StsGetParam(funcindex, "VIL");
            int result;
            double low = 0.0, high = {vcc}, epsilon = 0.001;

            vcc1.Set(FV, {vcc}f, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            dio.Connect();
            dio.SetPinLevel(4, 0, 3.4, 0.5);
            delay_ms(10);

            while (high - low > epsilon)
            {{
                double mid = (low + high) / 2;
                dio.SetChannelVIL(0, 0, mid);
                delay_us(500);
                dio.Run("T0", "T4");
                dio.GetBoardFailCount(0, result);
                if (result != 0) high = mid;
                else low = mid;
            }}
            VIL->SetTestResult(0, 0, high);
            VIL->SetResultRemark(0, 0, "A1");

            dio.Disconnect();
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            return 0;
        }}
    """),

    "VOH": textwrap.dedent("""
        DUT_API int VOH(short funcindex, LPCTSTR funclabel)
        {{
            CParam *VOH = StsGetParam(funcindex, "VOH");

            vcc1.Set(FV, {vcc_low}f, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            dio.Connect();
            dio.SetPinLevel(2.0, 0.7, 0, 0);
            delay_ms(5);
            dio.Run("T0", "T1");

            for (unsigned int i = 0; i < OutputPin_Int.size(); i++)
            {{
                Test_Value[i] = pmu.SetAndMeas(OutputPin_Int[i], FIMV, -400e-6, VRNG_10V, IRNG_1MA);
                VOH->SetTestResult(0, i, Test_Value[i]);
                VOH->SetResultRemark(0, i, OutputPin_String[i].c_str());
            }}

            pmu.Reset();
            dio.Disconnect();
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            return 0;
        }}
    """),

    "VOL": textwrap.dedent("""
        DUT_API int VOL(short funcindex, LPCTSTR funclabel)
        {{
            CParam *VOL1 = StsGetParam(funcindex, "VOL1");
            CParam *VOL2 = StsGetParam(funcindex, "VOL2");
            CParam* ParamArray[2] = {{ VOL1, VOL2 }};
            vector<double> LoadCurrent = {{ 4e-3, 8e-3 }};

            vcc1.Set(FV, {vcc_low}f, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            dio.Connect();
            dio.SetPinLevel(2.0, 0.8, 0, 0);
            delay_ms(5);
            dio.Run("T2", "T2");

            for (unsigned int i = 0; i < LoadCurrent.size(); i++)
                for (unsigned int j = 0; j < OutputPin_Int.size(); j++)
                {{
                    Test_Value[j] = pmu.SetAndMeas(OutputPin_Int[j], FIMV, LoadCurrent[i], VRNG_10V, IRNG_10MA);
                    ParamArray[i]->SetTestResult(0, j, Test_Value[j]);
                    ParamArray[i]->SetResultRemark(0, j, OutputPin_String[j].c_str());
                }}

            pmu.Reset();
            dio.Disconnect();
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            return 0;
        }}
    """),

    "IOS": textwrap.dedent("""
        DUT_API int IOS(short funcindex, LPCTSTR funclabel)
        {{
            CParam *IOS = StsGetParam(funcindex, "IOS");

            vcc1.Set(FV, {vcc_high}f, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            dio.Connect();
            dio.SetPinLevel(2.0, 0.7, 0, 0);
            delay_ms(5);
            dio.Run("T0", "T1");

            for (unsigned int i = 0; i < OutputPin_Int.size(); i++)
            {{
                Test_Value[i] = pmu.SetAndMeas(OutputPin_Int[i], FVMI, 0.0, VRNG_10V, IRNG_100MA);
                IOS->SetTestResult(0, i, Test_Value[i] * 1e3);
                IOS->SetResultRemark(0, i, OutputPin_String[i].c_str());
            }}

            pmu.Reset();
            dio.Disconnect();
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_us(500);
            return 0;
        }}
    """),

    "ICC": textwrap.dedent("""
        DUT_API int ICC(short funcindex, LPCTSTR funclabel)
        {{
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
        }}
    """),

    "LDO_DROPOUT": textwrap.dedent("""
        DUT_API int LDO_DROPOUT(short funcindex, LPCTSTR funclabel)
        {{
            // LDO 压降测试：逐步降低 VIN，找到 VOUT 开始下降的临界点
            CParam *DROPOUT = StsGetParam(funcindex, "DROPOUT");

            double vin_step = 0.05;
            double vin = {vcc};
            double vout_nom = {vout};
            double dropout_v = 0.0;

            // 输出端施加负载电流
            pmu.SetAndMeas({ldo_out_pin}, FIMV, -{load_ma}e-3, VRNG_10V, IRNG_1MA);
            delay_ms(5);

            for (vin = {vcc}; vin > 0.5; vin -= vin_step)
            {{
                vcc1.Set(FV, (float)vin, FOVI_10V, FOVI_100MA, RELAY_ON);
                delay_ms(10);
                double vout = pmu.SetAndMeas({ldo_out_pin}, FIMV, -{load_ma}e-3, VRNG_10V, IRNG_1MA);
                if (vout < vout_nom * 0.99)
                {{
                    dropout_v = vin - vout;
                    break;
                }}
            }}
            DROPOUT->SetTestResult(0, 0, dropout_v);
            DROPOUT->SetResultRemark(0, 0, "VIN-VOUT");

            pmu.Reset();
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);
            return 0;
        }}
    """),

    "LDO_ACCURACY": textwrap.dedent("""
        DUT_API int LDO_ACCURACY(short funcindex, LPCTSTR funclabel)
        {{
            // LDO 输出精度测试
            CParam *ACCURACY = StsGetParam(funcindex, "ACCURACY");

            vcc1.Set(FV, {vcc}f, FOVI_10V, FOVI_100MA, RELAY_ON);
            delay_ms(10);

            // 空载测量
            double vout = pmu.SetAndMeas({ldo_out_pin}, FIMV, -1e-6, VRNG_10V, IRNG_100UA);
            double error_pct = (vout - {vout}) / {vout} * 100.0;

            ACCURACY->SetTestResult(0, 0, error_pct);
            ACCURACY->SetResultRemark(0, 0, "VOUT_ERR%");

            pmu.Reset();
            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);
            return 0;
        }}
    """),

    "LDO_IQ": textwrap.dedent("""
        DUT_API int LDO_IQ(short funcindex, LPCTSTR funclabel)
        {{
            // LDO 静态电流测试（空载）
            CParam *IQ = StsGetParam(funcindex, "IQ");

            vcc1.Set(FV, {vcc}f, FOVI_10V, FOVI_10MA, RELAY_ON);
            delay_ms(10);

            vcc1.MeasureVI(10, 10);
            double iq = vcc1.GetMeasResult(0, MIRET, AVERAGE_RESULT);

            IQ->SetTestResult(0, 0, iq * 1e6); // 换算为 uA
            IQ->SetResultRemark(0, 0, "IQ_uA");

            vcc1.Set(FV, 0, FOVI_10V, FOVI_100MA, RELAY_OFF);
            return 0;
        }}
    """),
}


def _build_file_header(chip_name: str, chip_type: str, test_items: list[str], user_prompt: str) -> str:
    return textwrap.dedent(f"""
        /******************************************************************************
        * STS8200S 测试程序 - AI 自动生成
        *
        * 芯片名称：{chip_name}
        * 芯片类型：{chip_type}
        * 测试项目：{', '.join(test_items)}
        * 生成说明：{user_prompt}
        *
        * 注意：请在上机前由工程师复核所有参数值与引脚映射
        ******************************************************************************/
        #include "stdafx.h"
        #include "UserClass.h"
        #include <vector>
        using namespace std;

        // ── 电源与仪器声明 ────────────────────────────────────────
        FOVI vcc1(8, "vcc1");
        UserPMU pmu;
        UserDIO dio(0, 1, 2);

        double Test_Value[24] = {{ 0.0 }};
    """).strip()


def _build_pin_declarations(pin_names: list[str], input_pins: list[str], output_pins: list[str]) -> str:
    all_str = ', '.join(f'"{p}"' for p in pin_names)
    in_str  = ', '.join(f'"{p}"' for p in input_pins)
    out_str = ', '.join(f'"{p}"' for p in output_pins)
    all_int = ', '.join(str(i) for i in range(len(pin_names)))
    in_int  = ', '.join(str(i) for i, p in enumerate(pin_names) if p in input_pins)
    out_int = ', '.join(str(i) for i, p in enumerate(pin_names) if p in output_pins)

    return textwrap.dedent(f"""
        // ── 引脚定义 ──────────────────────────────────────────────
        vector<string> AllPin_String   = {{ {all_str} }};
        vector<string> InputPin_String = {{ {in_str} }};
        vector<string> OutputPin_String= {{ {out_str} }};

        vector<int> AllPin_Int    = {{ {all_int} }};
        vector<int> InputPin_Int  = {{ {in_int} }};
        vector<int> OutputPin_Int = {{ {out_int} }};
    """).strip()


def _build_callbacks(vcc: float) -> str:
    return textwrap.dedent(f"""
        // ── 硬件与生命周期回调 ────────────────────────────────────
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


def _build_template_code(item: str, params: dict) -> str:
    tpl = TEMPLATES.get(item, "")
    if not tpl:
        return ""
    try:
        return tpl.format(**params)
    except KeyError:
        return tpl


class CodegenService:
    """模板生成骨架 + DeepSeek AI 润色"""

    def __init__(self):
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
        chip_type: str,       # "digital" | "ldo" | "custom"
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
        pin_names    = pin_names    or ["A1","B1","Y1","A2","B2","Y2"]
        input_pins   = input_pins   or ["A1","B1","A2","B2"]
        output_pins  = output_pins  or ["Y1","Y2"]

        vcc_low  = round(vcc - 0.25, 2)
        vcc_high = round(vcc + 0.25, 2)
        fmt_params = dict(
            vcc=vcc, vcc_low=vcc_low, vcc_high=vcc_high,
            vout=vout, ldo_out_pin=ldo_out_pin, load_ma=load_ma,
        )

        # 1. 构建模板骨架
        sections = [
            _build_file_header(chip_name, chip_type, test_items, user_prompt),
            "",
            _build_pin_declarations(pin_names, input_pins, output_pins),
            "",
            _build_callbacks(vcc),
            "",
        ]

        for item in test_items:
            code = _build_template_code(item, fmt_params)
            if code:
                sections.append(code)
                sections.append("")

        skeleton_code = "\n".join(sections)

        # 2. RAG 增强生成 / AI 润色
        final_code      = skeleton_code
        ai_analysis     = []
        retrieved_chunks = []

        if self.client:
            # 尝试 RAG 增强生成
            rag_used = False
            if user_prompt.strip():
                try:
                    from app.services.rag_service import get_rag_service
                    rag_svc = get_rag_service()
                    if rag_svc.is_ready:
                        logger.info(" RAG 检索增强模式启动")
                        rag_code, retrieved_chunks = rag_svc.generate_with_rag(
                            user_query    = user_prompt,
                            chip_name     = chip_name,
                            chip_type     = chip_type,
                            skeleton_code = skeleton_code,
                            extra_context = f"芯片参数: VCC={vcc}V, VOUT={vout}V",
                        )
                        if rag_code and len(rag_code) > 100:
                            final_code = rag_code
                            rag_used   = True
                            logger.info(f"✅ RAG 生成完成: {len(final_code)} 字符, 检索 {len(retrieved_chunks)} 片段")
                except Exception as rag_e:
                    logger.warning(f"RAG 增强失败，降级到模板润色: {rag_e}")

            # 降级：模板 + AI 润色（无 RAG 或 RAG 失败时）
            if not rag_used and user_prompt.strip():
                try:
                    final_code, ai_analysis = self._ai_polish(
                        skeleton_code, chip_name, chip_type,
                        test_items, user_prompt, fmt_params,
                    )
                except Exception as e:
                    logger.warning(f"AI 润色失败，使用模板代码: {e}")

        lines = final_code.splitlines()
        return {
            "code":             final_code,
            "filename":         f"{chip_name.replace(' ', '_')}_test.cpp",
            "lines":            len(lines),
            "functions":        len([l for l in lines if "DUT_API int" in l]),
            "chip_name":        chip_name,
            "chip_type":        chip_type,
            "test_items":       test_items,
            "ai_analysis":      ai_analysis,
            "retrieved_chunks": retrieved_chunks,  # RAG 检索到的手册片段
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
        system_prompt = f"""你是 STS8200S ATE 测试机台的高级编程工程师。
{STS_API_REFERENCE}
你的任务：在不改变代码逻辑和结构的前提下：
1. 为每个测试函数添加专业的中文注释（说明测试目的、关键参数含义）
2. 根据用户描述"{user_prompt}"，调整注释中的参数说明和测试背景
3. 发现潜在问题时，用 // [WARNING] 标注
4. 不要删除、不要重写逻辑代码，只添加或改进注释
5. 直接返回完整 C++ 代码，不要任何 Markdown 格式"""

        user_msg = f"""芯片：{chip_name}（{chip_type}）
用户需求：{user_prompt}
参数：VCC={params['vcc']}V

以下是模板生成的骨架代码，请添加专业注释并返回完整代码：

{skeleton}"""

        resp = self.client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_msg},
            ],
            max_tokens=settings.MAX_TOKENS,
            temperature=0.3,
        )

        polished = resp.choices[0].message.content.strip()
        # 清理可能的 markdown 代码块
        if polished.startswith("```"):
            lines = polished.splitlines()
            polished = "\n".join(
                l for l in lines
                if not l.startswith("```")
            )

        # 提取 WARNING 注释作为分析提示
        warnings = [
            l.strip().lstrip("//").strip()
            for l in polished.splitlines()
            if "[WARNING]" in l
        ]

        return polished, warnings

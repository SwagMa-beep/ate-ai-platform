"""
LLM提取服务 - 面向STS8200S测试平台
支持三种测试场景的智能识别与参数提取
同时自动提取芯片引脚定义
"""
import instructor
import httpx
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple
import traceback
import os
import json
import re
import time

from app.models.testplan import (
    TestPlan, DCParam, PinDefinition,
    DIGITAL_DC_PARAMS, DIGITAL_AC_PARAMS,
    LDO_PARAMS, EEPROM_PARAMS,
    STS8200S_LIMITS
)
from app.core.config import get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()

CHIP_DETECT_MAX_TOKENS = 32
EXTRACTION_MAX_TOKENS = min(settings.MAX_TOKENS, 5000)
LLM_READ_TIMEOUT_SECONDS = 90.0
LLM_MAX_RETRIES = 1
VALID_CHIP_TYPES = {
    "DIGITAL_74", "DIGITAL_54", "DIGITAL_4000",
    "MEMORY", "LDO", "EEPROM", "ANALOG_GENERAL", "UNKNOWN",
}
VALID_TEST_SCENARIOS = {"DIGITAL_DC", "DIGITAL_AC", "LDO", "EEPROM", "GENERAL"}
VALID_PIN_DIRECTIONS = {"IN", "OUT", "PWR", "GND", "BIDIR", "NC"}
NUMERIC_FIELDS = {
    "min_val", "typ_val", "max_val",
    "voltage_max", "current_max",
    "confidence",
}
EXTRACTION_JSON_CONTRACT = """Return only this JSON object:
{
  "chip_name": "",
  "chip_type": "DIGITAL_74|DIGITAL_54|DIGITAL_4000|MEMORY|LDO|EEPROM|ANALOG_GENERAL|UNKNOWN",
  "dc_params": [
    {
      "param_name": "",
      "category": "A|B|C",
      "test_scenario": "DIGITAL_DC|DIGITAL_AC|LDO|EEPROM|GENERAL",
      "condition": "",
      "min_val": null,
      "typ_val": null,
      "max_val": null,
      "unit": "",
      "confidence": 0.9,
      "sts_test_function": "FOVI_Test|DIO_Test|QTMU_Test|ACSM_Test"
    }
  ],
  "pin_definitions": [
    {
      "pin_no": 1,
      "pin_name": "",
      "function": "",
      "direction": "IN|OUT|PWR|GND|BIDIR|NC",
      "voltage_max": null,
      "current_max": null,
      "notes": ""
    }
  ]
}
Use [] when no params or pins. Use null for unknown numeric values."""


class LLMExtractor:
    """LLM参数提取器 - STS8200S专用"""

    def __init__(self):
        if not settings.DEEPSEEK_API_KEY:
            logger.error("❌ DEEPSEEK_API_KEY未配置")
            raise ValueError(
                "DEEPSEEK_API_KEY未配置，请检查backend/.env文件"
            )

        # 清除代理环境变量
        for proxy_var in [
            "HTTP_PROXY", "HTTPS_PROXY",
            "http_proxy", "https_proxy",
            "ALL_PROXY", "all_proxy"
        ]:
            if proxy_var in os.environ:
                logger.info(f"Cleanup proxy: {proxy_var}")
                del os.environ[proxy_var]

        # 自定义httpx客户端，解决SSL握手超时问题
        http_client = httpx.Client(
            timeout=httpx.Timeout(
                connect=30.0,
                read=LLM_READ_TIMEOUT_SECONDS,
                write=30.0,
                pool=30.0
            ),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=30.0
            ),
            verify=False  # 关闭SSL验证，解决握手超时
        )
        self.raw_client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            http_client=http_client,
            timeout=LLM_READ_TIMEOUT_SECONDS,
            max_retries=LLM_MAX_RETRIES,
        )
        instructor_base_client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            http_client=httpx.Client(
                timeout=httpx.Timeout(
                    connect=30.0,
                    read=LLM_READ_TIMEOUT_SECONDS,
                    write=30.0,
                    pool=30.0
                ),
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=10,
                    keepalive_expiry=30.0
                ),
                verify=False
            ),
            timeout=LLM_READ_TIMEOUT_SECONDS,
            max_retries=LLM_MAX_RETRIES,
        )
        # Support both old and new instructor APIs.
        if hasattr(instructor, "from_openai"):
            self.client = instructor.from_openai(instructor_base_client)
        elif hasattr(instructor, "patch"):
            self.client = instructor.patch(instructor_base_client)
        else:
            raise RuntimeError(
                "Unsupported instructor package version. "
                "Please install a compatible instructor release."
            )

        logger.info(
            f"LLM Client initialized: {settings.DEEPSEEK_MODEL} | "
            f"Key: {settings.DEEPSEEK_API_KEY[:8]}..."
        )

    @staticmethod
    def _extract_json_text(content: str) -> str:
        """Best-effort extraction for JSON returned with markdown fences or extra prose."""
        text = (content or "").strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
        if fenced:
            return fenced.group(1).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start:end + 1]
        return text

    @staticmethod
    def _empty_to_none(value):
        if value in ("", "N/A", "NA", "-", "--"):
            return None
        return value

    @classmethod
    def _normalize_payload(cls, payload: Dict) -> Dict:
        """Normalize compact LLM JSON before Pydantic validation."""
        if not isinstance(payload, dict):
            return {}

        normalized = {
            "chip_name": payload.get("chip_name") or "",
            "chip_type": (payload.get("chip_type") or "UNKNOWN").upper(),
            "dc_params": [],
            "pin_definitions": [],
        }
        if normalized["chip_type"] not in VALID_CHIP_TYPES:
            normalized["chip_type"] = "UNKNOWN"

        params = payload.get("dc_params") or []
        if not isinstance(params, list):
            params = []
        for item in params:
            if not isinstance(item, dict):
                continue

            param = dict(item)
            for field in ["param_name", "category", "test_scenario", "condition", "unit"]:
                if param.get(field) is None:
                    param[field] = ""
                else:
                    param[field] = str(param.get(field)).strip()

            if not param["param_name"]:
                continue
            if param["category"] not in {"A", "B", "C"}:
                param["category"] = "A"
            if param["test_scenario"] not in VALID_TEST_SCENARIOS:
                param["test_scenario"] = "GENERAL"

            for field in NUMERIC_FIELDS:
                if field in param:
                    param[field] = cls._empty_to_none(param[field])

            normalized["dc_params"].append(param)

        pins = payload.get("pin_definitions") or []
        if not isinstance(pins, list):
            pins = []
        for item in pins:
            if not isinstance(item, dict):
                continue

            pin = dict(item)
            try:
                pin["pin_no"] = int(pin.get("pin_no"))
            except (TypeError, ValueError):
                continue

            for field in ["pin_name", "function", "notes"]:
                if pin.get(field) is None:
                    pin[field] = ""
                else:
                    pin[field] = str(pin.get(field)).strip()

            direction = str(pin.get("direction") or "IN").strip().upper()
            pin["direction"] = direction if direction in VALID_PIN_DIRECTIONS else "IN"
            for field in NUMERIC_FIELDS:
                if field in pin:
                    pin[field] = cls._empty_to_none(pin[field])

            normalized["pin_definitions"].append(pin)

        return normalized

    def _create_structured_plan(self, prompt: str, max_tokens: int = EXTRACTION_MAX_TOKENS) -> TestPlan:
        """Use plain chat completion + JSON parsing to avoid instructor/function-call incompatibility."""
        completion = self.raw_client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Return only a valid JSON object. "
                        "Do not include markdown fences, explanations, or extra text."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"{prompt}\n\n"
                        f"{EXTRACTION_JSON_CONTRACT}"
                    ),
                },
            ],
            temperature=settings.TEMPERATURE,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content or "{}"
        json_text = self._extract_json_text(content)
        payload = self._normalize_payload(json.loads(json_text))

        return TestPlan.model_validate(payload)

    # ----------------------------------------------------------
    # 公共方法
    # ----------------------------------------------------------

    def detect_chip_type(self, first_chunks: List[Dict]) -> str:
        """
        第一阶段：从PDF前几页识别芯片类型
        """
        combined_text = "\n".join(
            [c["content"][:1000] for c in first_chunks[:3]]
        )

        prompt = f"""你是ATE测试工程师，分析以下芯片Datasheet片段，判断芯片类型。

    【芯片类型定义】
    - DIGITAL_74: 74系列数字逻辑芯片 (74HC/74LS/74HCT/74ALS/HD74/SN74/MC74等前缀)
    - DIGITAL_54: 54系列军品数字逻辑芯片
    - DIGITAL_4000: 4000系列CMOS数字芯片 (CD4000/HEF4000等)
    - MEMORY: 存储器芯片 (SRAM/DRAM等，不含EEPROM)
    - LDO: 线性稳压器 (如L7805/LM317/LM7805/AMS1117等)
    - EEPROM: 串行EEPROM (如AT24C01/AT24C02，有I2C/SPI接口)
    - ANALOG_GENERAL: 其他模拟芯片
    - UNKNOWN: 无法判断

    【判断规则（按优先级从高到低）】
    1. 型号含 HD74/SN74/MC74/74HC/74LS/74HCT/74ALS → DIGITAL_74
    2. 型号含 54LS/54HC/54HCT → DIGITAL_54
    3. 型号含 CD4000/HEF4000/4001/4011/4013 → DIGITAL_4000
    4. 关键词含 I2C/SDA/SCL 且 EEPROM/Serial Memory → EEPROM
    5. 关键词含 VIN/VOUT/dropout/regulator/稳压 → LDO
    6. 参数表含 VIH/VIL/VOH/VOL/tPHL/tPLH → DIGITAL_74
    7. 参数表含 VO/Sv/Si/Iq → LDO

    【重要示例】
    - HD74LS00P → DIGITAL_74（HD74前缀）
    - SN74HC00N → DIGITAL_74（SN74前缀）
    - L7805CV   → LDO（稳压器）
    - AT24C01   → EEPROM（I2C接口）

    Datasheet片段：
    {combined_text}

    只返回芯片类型字符串，不要任何其他内容和解释。
    可选值：DIGITAL_74 / DIGITAL_54 / DIGITAL_4000 / MEMORY / LDO / EEPROM / ANALOG_GENERAL / UNKNOWN"""

        try:
            resp = self.raw_client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=CHIP_DETECT_MAX_TOKENS,
            )
            chip_type = (resp.choices[0].message.content or "").strip().upper()

            # ✅ 清理多余字符（AI有时会返回带引号/换行/空格的内容）
            chip_type = (
                chip_type
                .replace('"', '')
                .replace("'", '')
                .replace("\n", '')
                .strip()
            )

            # ✅ 模糊匹配容错（AI返回内容包含关键词时自动修正）
            if any(k in chip_type for k in ["74", "HD74", "SN74", "DIGITAL_74"]):
                chip_type = "DIGITAL_74"
            elif "54" in chip_type and "DIGITAL" in chip_type:
                chip_type = "DIGITAL_54"
            elif "4000" in chip_type:
                chip_type = "DIGITAL_4000"
            elif "EEPROM" in chip_type:
                chip_type = "EEPROM"
            elif any(k in chip_type for k in ["LDO", "REGULATOR"]):
                chip_type = "LDO"
            elif "MEMORY" in chip_type:
                chip_type = "MEMORY"
            elif "ANALOG" in chip_type:
                chip_type = "ANALOG_GENERAL"

            valid_types = {
                "DIGITAL_74", "DIGITAL_54", "DIGITAL_4000",
                "MEMORY", "LDO", "EEPROM", "ANALOG_GENERAL", "UNKNOWN"
            }
            if chip_type not in valid_types:
                logger.warning(f"AI returned unknown type: [{chip_type}], setting to UNKNOWN")
                chip_type = "UNKNOWN"

            logger.info(f"Chip detection: {chip_type}")
            return chip_type

        except Exception as e:
            logger.warning(f"Chip type detection failed: {e}")
            return "UNKNOWN"
    def extract_from_chunk(
            self,
            chunk: Dict,
            chip_type: str = "UNKNOWN"
    ) -> TestPlan:
        """从单个PDF片段提取参数和引脚定义"""
        if chip_type in {
            "DIGITAL_74", "DIGITAL_54", "DIGITAL_4000", "MEMORY"
        }:
            prompt = self._build_digital_prompt(chunk)
        elif chip_type == "LDO":
            prompt = self._build_ldo_prompt(chunk)
        elif chip_type == "EEPROM":
            prompt = self._build_eeprom_prompt(chunk)
        else:
            prompt = self._build_general_prompt(chunk)

        prompt_chars = len(prompt)
        chunk_t0 = time.perf_counter()
        try:
            resp = self._create_structured_plan(prompt, max_tokens=EXTRACTION_MAX_TOKENS)
            elapsed = time.perf_counter() - chunk_t0

            for param in resp.dc_params:
                if isinstance(chunk["page"], int):
                    param.page = chunk["page"]
                if chip_type in {
                    "DIGITAL_74", "DIGITAL_54", "DIGITAL_4000"
                }:
                    if param.param_name in DIGITAL_AC_PARAMS:
                        param.test_scenario = "DIGITAL_AC"
                    elif param.param_name in DIGITAL_DC_PARAMS:
                        param.test_scenario = "DIGITAL_DC"
                elif chip_type == "LDO":
                    param.test_scenario = "LDO"
                elif chip_type == "EEPROM":
                    param.test_scenario = "EEPROM"

            resp.chip_type = chip_type

            logger.debug(
                f"Page {chunk['page']}: "
                f"params {len(resp.dc_params)}, "
                f"pins {len(resp.pin_definitions)}"
            )
            logger.info(
                f"[perf] llm_chunk page={chunk['page']} cost={elapsed:.2f}s "
                f"input_chars={prompt_chars} params={len(resp.dc_params)} "
                f"pins={len(resp.pin_definitions)}"
            )
            return resp

        except Exception as e:
            elapsed = time.perf_counter() - chunk_t0
            logger.error(
                f"Page {chunk['page']} extraction failed: "
                f"{type(e).__name__}: {e}"
            )
            logger.info(
                f"[perf] llm_chunk page={chunk['page']} cost={elapsed:.2f}s "
                f"input_chars={prompt_chars} status=failed"
            )
            logger.error(traceback.format_exc())
            return TestPlan()

    def extract_parallel(
        self,
        chunks: List[Dict],
        chip_type: str = "UNKNOWN",
        max_workers: Optional[int] = None,
        progress_callback = None
    ) -> Tuple[List[DCParam], List[PinDefinition]]:
        """并发提取多个页面"""
        max_workers  = max_workers or settings.MAX_WORKERS
        all_params   = []
        all_pins_map = {}

        logger.info(
            f"开始并发提取 | 芯片类型: {chip_type} | "
            f"并发数: {max_workers} | 页数: {len(chunks)}"
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_chunk = {
                executor.submit(
                    self.extract_from_chunk, chunk, chip_type
                ): chunk
                for chunk in chunks
            }

            finished_count = 0
            for future in as_completed(future_to_chunk):
                finished_count += 1
                chunk = future_to_chunk[future]
                try:
                    plan = future.result()
                    if plan:
                        if plan.dc_params:
                            all_params.extend(plan.dc_params)
                            logger.debug(
                                f"  第{chunk['page']}页提取到"
                                f"{len(plan.dc_params)}个参数"
                            )
                        for pin in plan.pin_definitions:
                            if pin.pin_no not in all_pins_map:
                                all_pins_map[pin.pin_no] = pin

                except Exception as exc:
                    logger.error(
                        f"Page {chunk['page']} task error: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    logger.error(traceback.format_exc())

                if progress_callback:
                    try:
                        progress_callback(finished_count, len(chunks))
                    except Exception as e:
                        logger.warning(f"Progress callback failed: {e}")



        # 按引脚号排序
        all_pins = sorted(
            all_pins_map.values(),
            key=lambda p: p.pin_no
        )

        logger.info(
            f"Parallel extraction done | Params: {len(all_params)} | "
            f"Pins: {len(all_pins)}"
        )
        return all_params, all_pins

    # ----------------------------------------------------------
    # 私有方法：引脚提取通用指令
    # ----------------------------------------------------------

    def _pin_extract_instruction(self, chip_type: str) -> str:
        """生成引脚提取通用指令"""
        examples = {
            "DIGITAL": """
示例（74LS00四与非门，14引脚）：
  pin_no=1,  pin_name="1A",  direction="IN",  function="第1门输入A"
  pin_no=2,  pin_name="1B",  direction="IN",  function="第1门输入B"
  pin_no=3,  pin_name="1Y",  direction="OUT", function="第1门输出"
  pin_no=7,  pin_name="GND", direction="GND", function="地"
  pin_no=14, pin_name="VCC", direction="PWR", function="电源(5V)"
""",
            "LDO": """
示例（L7805CV，TO-220封装，3引脚）：
  pin_no=1, pin_name="VIN",  direction="IN",  function="输入电压"
  pin_no=2, pin_name="GND",  direction="GND", function="地"
  pin_no=3, pin_name="VOUT", direction="OUT", function="输出电压(5V)"
""",
            "EEPROM": """
示例（AT24C01，SOP8封装，8引脚）：
  pin_no=1, pin_name="A0",  direction="IN",    function="I2C地址位0"
  pin_no=2, pin_name="A1",  direction="IN",    function="I2C地址位1"
  pin_no=3, pin_name="A2",  direction="IN",    function="I2C地址位2"
  pin_no=4, pin_name="GND", direction="GND",   function="地"
  pin_no=5, pin_name="SDA", direction="BIDIR", function="I2C数据线"
  pin_no=6, pin_name="SCL", direction="IN",    function="I2C时钟线"
  pin_no=7, pin_name="WP",  direction="IN",    function="写保护"
  pin_no=8, pin_name="VCC", direction="PWR",   function="电源"
""",
        }

        key = (
            "DIGITAL"
            if "DIGITAL" in chip_type or chip_type == "MEMORY"
            else chip_type if chip_type in examples
            else "LDO"
        )

        return f"""
【同时提取：引脚定义表 → pin_definitions字段】
如果本页包含以下内容，请提取所有引脚信息：
  - Pin Description / Pin Configuration
  - 引脚说明 / 管脚描述 / 引脚功能表

每个引脚填写：
  pin_no      : 引脚编号(整数，从1开始)
  pin_name    : 引脚名称(与Datasheet完全一致)
  function    : 功能描述(简短说明)
  direction   : IN / OUT / PWR / GND / BIDIR / NC
  voltage_max : 最大电压(V)，没有则填null
  notes       : 特殊说明

direction判断规则：
  输入信号引脚   → IN
  输出信号引脚   → OUT
  双向信号引脚   → BIDIR
  电源/VCC引脚  → PWR
  地/GND引脚    → GND
  未连接引脚     → NC
{examples.get(key, "")}
如果本页没有引脚表，pin_definitions返回空列表[]。
"""

    # ----------------------------------------------------------
    # 私有方法：场景化Prompt构建
    # ----------------------------------------------------------

    def _build_digital_prompt(self, chunk: Dict) -> str:
        """场景A：数字芯片测试Prompt"""
        dc_params_str   = "/".join(sorted(DIGITAL_DC_PARAMS))
        ac_params_str   = "/".join(sorted(DIGITAL_AC_PARAMS))
        pin_instruction = self._pin_extract_instruction("DIGITAL")

        return f"""你是资深ATE测试工程师，专注于STS8200S测试机台的数字芯片测试。
从Datasheet片段中提取测试参数和引脚定义。

【必须提取的DC参数】（param_name必须从以下选择）
{dc_params_str}

【必须提取的AC参数】（param_name必须从以下选择）
{ac_params_str}

【condition字段要求】
DC参数: "VCC=5V, VIH=3.5V, VIL=1.5V, IOH=-0.4mA, Ta=25℃"
AC参数: "VCC=5V, CL=50pF, RL=1kΩ, tr=tf=6ns, Ta=25℃"

【category字段说明】
A=电气特性(有Min/Max限值), B=绝对最大额定值, C=推荐工作条件

【sts_test_function字段】
- DC参数(VIH/VIL/VOH/VOL等) → "FOVI_Test"
- 数字功能(FUN/CONNECT)      → "DIO_Test"
- 精密电流(II/IIH/IIL等)     → "QTMU_Test"
- AC参数(Tr/Tf/tPHL/tPLH)   → "ACSM_Test"

{pin_instruction}

注意：这可能是一段合并了多个连续页面的长文本，请提取其中包含的所有相关参数和引脚。
片段内容（页码 {chunk['page']}）：
{chunk['content']}
"""

    def _build_ldo_prompt(self, chunk: Dict) -> str:
        """场景B1：线性稳压器(LDO)测试Prompt"""
        pin_instruction = self._pin_extract_instruction("LDO")

        return f"""你是资深ATE测试工程师，专注于STS8200S测试机台的模拟芯片测试。
从Datasheet片段中提取LDO测试参数和引脚定义。

【必须提取的LDO参数】
- VO : 输出电压，condition示例: "VIN=10V, IOUT=500mA, Ta=25℃"
- Sv : 线性调整率，condition示例: "IOUT=500mA, VIN从7V到25V, Ta=25℃"
- Si : 负载调整率，condition示例: "VIN=10V, IOUT从5mA到1.5A, Ta=25℃"
- Iq : 静态电流，condition示例: "VIN=10V, IOUT=0, Ta=25℃"

【sts_test_function字段】
- DC测试(如VO/Sv/Si/Iq) → "FOVI_Test"或"QTMU_Test"

{pin_instruction}

注意：这可能是一段合并了多个连续页面的长文本，请提取其中包含的所有相关参数和引脚。
片段内容（页码 {chunk['page']}）：
{chunk['content']}
"""

    def _build_eeprom_prompt(self, chunk: Dict) -> str:
        """场景B2：EEPROM测试Prompt"""
        pin_instruction = self._pin_extract_instruction("EEPROM")

        return f"""你是资深ATE测试工程师，专注于STS8200S测试机台的EEPROM测试。
从Datasheet片段中提取EEPROM的测试参数和引脚定义。

【提取电气参数】
A类电气特性：VIH/VIL/VOL/IOL/ICC/ISB
B类绝对最大值：VCC最大电压、各引脚最大电压
C类工作条件：VCC范围、工作温度范围、fSCL最大频率

【sts_test_function字段】
请根据参数特点推测：
- 引脚状态或逻辑测试     → "DIO_Test"
- 小于100mA的电流测试   → "QTMU_Test"
- 电压或大电流测试      → "FOVI_Test"
- 带有时间(ns/us)的参数 → "ACSM_Test"

{pin_instruction}

注意：这可能是一段合并了多个连续页面的长文本，请提取其中包含的所有相关参数和引脚。
片段内容（页码 {chunk['page']}）：
{chunk['content']}
"""

    def _build_general_prompt(self, chunk: Dict) -> str:
        """场景C：通用模拟芯片测试Prompt"""
        pin_instruction = self._pin_extract_instruction("LDO")

        return f"""你是资深ATE测试工程师，使用STS8200S测试机台。
从Datasheet片段中提取电气参数和引脚定义。

【STS8200S硬件资源限制】
- VI源最大电压: {STS8200S_LIMITS['VI_voltage_max']}V
- VI源最大电流: {STS8200S_LIMITS['VI_current_max'] * 1000}mA
- DIO通道电压范围: {STS8200S_LIMITS['DIO_voltage_low']}V ~ {STS8200S_LIMITS['DIO_voltage_high']}V

【三类参数定义】
A类: 电气特性(有Min/Typ/Max的可测试参数)
B类: 绝对最大额定值
C类: 推荐工作条件

【不要提取】
热阻参数(θJA/θJC等)、封装尺寸

【sts_test_function字段参考】
- 电压/电流参数 → "FOVI_Test"
- 精密小电流    → "QTMU_Test"

{pin_instruction}

片段内容（第{chunk['page']}页）：
{chunk['content']}
"""

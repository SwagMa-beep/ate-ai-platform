"""
模块三：测试代码生成 API
POST /api/v1/codegen/generate
"""
from fastapi import APIRouter, Body
from typing import Optional
from pydantic import BaseModel, Field

from app.services.codegen_service import CodegenService
from app.services.code_validator import CodeValidator
from app.core.response import success, error
from app.utils.logger import setup_logger

logger    = setup_logger()
router    = APIRouter()
service   = CodegenService()
validator = CodeValidator()



class CodegenRequest(BaseModel):
    chip_name:   str        = Field("MyChip",   description="芯片型号名称")
    chip_type:   str        = Field("digital",  description="芯片类型: digital | ldo | custom")
    test_items:  list[str]  = Field(["CON","FUN"], description="测试项列表")
    user_prompt: str        = Field("",         description="用户自然语言描述")
    # 引脚配置（可选，模块一提取后自动填入）
    pin_names:    Optional[list[str]] = Field(None, description="所有引脚名称列表")
    input_pins:   Optional[list[str]] = Field(None, description="输入引脚名称列表")
    output_pins:  Optional[list[str]] = Field(None, description="输出引脚名称列表")
    # 电气参数
    vcc:          float = Field(5.0,  description="电源电压(V)")
    vout:         float = Field(3.3,  description="LDO 输出电压(V)，仅 ldo 类型使用")
    ldo_out_pin:  int   = Field(2,    description="LDO 输出引脚 DIO 编号")
    load_ma:      float = Field(100.0, description="负载电流(mA)，仅 ldo 类型使用")


@router.post("/generate", summary="AI 生成 STS8200S 测试代码")
async def generate_code(req: CodegenRequest = Body(...)):
    """
    根据芯片类型、测试项和用户描述，生成 STS8200S C++ 测试程序。

    **策略**：模板生成骨架代码 → DeepSeek AI 添加专业注释与分析
    """
    logger.info(
        f" 代码生成请求: chip={req.chip_name}, "
        f"type={req.chip_type}, items={req.test_items}"
    )

    # 验证测试项
    valid_digital = {"CON","FUN","VIH","VIL","VIK","VOH","VOL","IOS","II","IIN","ICC","TP1","TP2","TP3","TP4"}
    valid_ldo     = {"LDO_DROPOUT","LDO_ACCURACY","LDO_IQ"}
    valid_items   = valid_digital | valid_ldo

    unknown = [i for i in req.test_items if i not in valid_items]
    if unknown:
        return error(f"未知测试项: {unknown}，支持的测试项: {sorted(valid_items)}", code=400)

    if not req.test_items:
        return error("至少选择一个测试项", code=400)

    try:
        result = service.generate(
            chip_name    = req.chip_name,
            chip_type    = req.chip_type,
            test_items   = req.test_items,
            user_prompt  = req.user_prompt,
            pin_names    = req.pin_names,
            input_pins   = req.input_pins,
            output_pins  = req.output_pins,
            vcc          = req.vcc,
            vout         = req.vout,
            ldo_out_pin  = req.ldo_out_pin,
            load_ma      = req.load_ma,
        )

        # P3: 静态代码校验
        static_analysis = {}
        try:
            analysis = validator.validate(result.get("code", ""))
            static_analysis = analysis.to_dict()
        except Exception as ve:
            logger.warning(f"静态校验异常（不影响代码输出）: {ve}")

        result["static_analysis"] = static_analysis

        logger.info(
            f"✅ 代码生成完成: {result['lines']} 行, "
            f"{result['functions']} 个测试函数 | "
            f"校验评分: {static_analysis.get('score', 'N/A')}"
        )
        return success(data=result, message="代码生成成功")

    except Exception as e:
        logger.error(f"❌ 代码生成失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return error(f"代码生成失败: {str(e)}", code=500)



@router.get("/templates", summary="获取支持的测试项列表")
async def list_templates():
    """返回所有支持的测试项及其说明"""
    return success(data={
        "digital": [
            {"id": "CON",  "name": "连通性测试",       "desc": "接触电阻/断路检测"},
            {"id": "FUN",  "name": "功能逻辑测试",     "desc": "运行数字向量验证逻辑"},
            {"id": "VIH",  "name": "输入高电平阈值",   "desc": "最小 VIH 扫描"},
            {"id": "VIL",  "name": "输入低电平阈值",   "desc": "最大 VIL 二分法"},
            {"id": "VOH",  "name": "输出高电平",       "desc": "输出高电平电压"},
            {"id": "VOL",  "name": "输出低电平",       "desc": "输出低电平电压（双负载）"},
            {"id": "IOS",  "name": "输出短路电流",     "desc": "输出引脚强制至 0V 测量电流"},
            {"id": "ICC",  "name": "电源电流",         "desc": "高/低态供电电流"},
        ],
        "ldo": [
            {"id": "LDO_DROPOUT",  "name": "压降测试",     "desc": "逐步降低 VIN 找临界压差"},
            {"id": "LDO_ACCURACY", "name": "输出精度",     "desc": "空载 VOUT 精度百分比"},
            {"id": "LDO_IQ",       "name": "静态电流",     "desc": "空载 IQ(uA)测量"},
        ],
    }, message="查询成功")

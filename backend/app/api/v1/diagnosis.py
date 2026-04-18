"""
良率诊断 API - 目标④
提供 ML 驱动的量产良率诊断与波形分析接口
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional

from app.services.yield_diagnosis import YieldDiagnosisService
from app.core.response import success, error
from app.utils.logger import setup_logger

logger  = setup_logger()
router  = APIRouter()
_svc    = YieldDiagnosisService()   # 单例，保留历史良率


class DiagnosisRequest(BaseModel):
    n_samples:      int   = Field(200, ge=50,  le=2000, description="采样点数")
    inject_anomaly: bool  = Field(True,                  description="注入模拟异常")
    anomaly_ratio:  float = Field(0.08, ge=0.0, le=0.5, description="异常比例")
    channel:        int   = Field(4,   ge=0,   le=23,   description="诊断 DIO 通道号")


@router.post("/run", summary="运行良率诊断分析")
async def run_diagnosis(req: DiagnosisRequest):
    """
    触发一次完整的 ML 良率诊断：
    - 生成仿真 VI 波形数据（符合 ATE 量产分布）
    - IsolationForest 无监督异常检测
    - 线性回归预测 T+4H 良率趋势
    - 返回故障分类与波形数据
    """
    try:
        result = _svc.run_diagnosis(
            n_samples      = req.n_samples,
            inject_anomaly = req.inject_anomaly,
            anomaly_ratio  = req.anomaly_ratio,
            channel        = req.channel,
        )
        logger.info(
            f" 诊断完成: 良率={result.yield_rate}% | "
            f"异常率={result.anomaly_ratio:.1%} | "
            f"耗时={result.analysis_time_ms:.0f}ms"
        )
        return success(data=result.to_dict(), message="诊断分析完成")
    except Exception as e:
        logger.error(f"诊断失败: {e}")
        return error(f"诊断失败: {str(e)}", code=500)


@router.get("/waveform", summary="获取最新仿真波形数据")
async def get_waveform(
    n_points:       int  = Query(100, ge=20,  le=1000),
    inject_anomaly: bool = Query(True),
):
    """获取一段最新的仿真 VI 波形（用于前端实时波形展示）"""
    try:
        result = _svc.run_diagnosis(
            n_samples      = n_points,
            inject_anomaly = inject_anomaly,
            anomaly_ratio  = 0.08,
        )
        return success(data={
            "waveform":     result.waveform,
            "yield_rate":   result.yield_rate,
            "anomaly_ratio": result.anomaly_ratio,
        }, message="获取成功")
    except Exception as e:
        return error(str(e), code=500)

"""
Yield diagnosis API.
"""

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.response import error, success
from app.services.workspace_memory_service import get_workspace_memory_service
from app.services.yield_diagnosis import YieldDiagnosisService
from app.utils.logger import setup_logger

logger = setup_logger()
router = APIRouter()
_svc = YieldDiagnosisService()
workspace_memory = get_workspace_memory_service()


class DiagnosisRequest(BaseModel):
    n_samples: int = Field(200, ge=50, le=2000, description="Sample count")
    inject_anomaly: bool = Field(True, description="Inject simulated anomalies")
    anomaly_ratio: float = Field(0.08, ge=0.0, le=0.5, description="Anomaly ratio")
    channel: int = Field(4, ge=0, le=23, description="Diagnosed DIO channel")


@router.post("/run", summary="Run yield diagnosis analysis")
async def run_diagnosis(req: DiagnosisRequest):
    try:
        result = _svc.run_diagnosis(
            n_samples=req.n_samples,
            inject_anomaly=req.inject_anomaly,
            anomaly_ratio=req.anomaly_ratio,
            channel=req.channel,
        )
        workspace_memory.update_failure_context(
            {
                "topic": f"channel-{req.channel}",
                "summary": (
                    f"良率 {result.yield_rate}% / 异常比例 {result.anomaly_ratio:.1%} / "
                    f"样本 {result.sample_count} / 耗时 {result.analysis_time_ms:.0f}ms"
                ),
            }
        )
        logger.info(
            "Diagnosis finished: yield=%s%% anomaly=%s analysis=%.0fms",
            result.yield_rate,
            f"{result.anomaly_ratio:.1%}",
            result.analysis_time_ms,
        )
        return success(data=result.to_dict(), message="诊断分析完成")
    except Exception as exc:
        logger.error(f"Diagnosis failed: {exc}")
        return error(f"诊断失败: {exc}", code=500)


@router.get("/waveform", summary="Get latest simulated waveform")
async def get_waveform(
    n_points: int = Query(100, ge=20, le=1000),
    inject_anomaly: bool = Query(True),
):
    try:
        result = _svc.run_diagnosis(
            n_samples=n_points,
            inject_anomaly=inject_anomaly,
            anomaly_ratio=0.08,
        )
        return success(
            data={
                "waveform": result.waveform,
                "yield_rate": result.yield_rate,
                "anomaly_ratio": result.anomaly_ratio,
            },
            message="获取成功",
        )
    except Exception as exc:
        return error(str(exc), code=500)

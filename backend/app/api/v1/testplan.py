"""
TestPlan API端点 - 模块一
统一响应格式，支持前后端分离
"""
from fastapi import (
    APIRouter, UploadFile, File,
    HTTPException, BackgroundTasks, Query
)
from fastapi.responses import FileResponse
from typing import Optional
from pathlib import Path
import uuid
from datetime import datetime

from app.services.testplan_service import TestPlanService
from app.core.config import get_settings
from app.core.response import success, error, paginate
from app.utils.logger import setup_logger

settings = get_settings()
logger   = setup_logger()
router   = APIRouter()
service  = TestPlanService()

# 任务状态存储（生产环境用Redis）
task_status: dict = {}


# ============================================================
# 文件上传
# ============================================================

@router.post("/upload", summary="上传Datasheet PDF")
async def upload_pdf(
    file: UploadFile = File(..., description="PDF文件，最大50MB")
):
    """
    上传Datasheet PDF文件

    **返回：**
    - file_id: 文件唯一ID，后续接口使用
    - filename: 原始文件名
    - size_mb: 文件大小(MB)
    """
    # 验证文件类型
    if not file.filename.lower().endswith(".pdf"):
        return error("只支持PDF文件，请上传.pdf格式", code=400)

    # 读取并验证大小
    contents  = await file.read()
    file_size = len(contents)

    if file_size > 50 * 1024 * 1024:
        return error(
            f"文件大小超过50MB限制，"
            f"当前: {file_size / 1024 / 1024:.1f}MB",
            code=400
        )

    if file_size == 0:
        return error("文件内容为空", code=400)

    # 生成唯一文件ID
    file_id       = str(uuid.uuid4())[:8]
    timestamp     = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = file.filename.replace(" ", "_")
    file_path     = (
        settings.UPLOAD_DIR
        / f"{file_id}_{timestamp}_{safe_filename}"
    )

    try:
        with file_path.open("wb") as f:
            f.write(contents)

        logger.info(
            f"File uploaded: {file.filename} "
            f"({file_size / 1024:.1f}KB)"
        )

        return success(
            data={
                "file_id":     file_id,
                "filename":    file.filename,
                "size":        file_size,
                "size_mb":     round(file_size / 1024 / 1024, 2),
                "upload_time": timestamp,
            },
            message="文件上传成功"
        )

    except Exception as e:
        logger.error(f"File save failed: {e}")
        return error(f"文件保存失败: {str(e)}", code=500)


# ============================================================
# 同步提取
# ============================================================

@router.post("/extract", summary="提取TestPlan（同步）")
async def extract_testplan(
        file_id: str = Query(..., description="上传文件返回的ID"),
        pages: Optional[str] = Query(None, description="页码范围，如3-9"),
        max_workers: int = Query(5, description="并发数1-10", ge=1, le=10),
        chip_type: Optional[str] = Query(None, description="手动指定芯片类型（可选）")
):
    # ── 查找上传的文件 ────────────────────────────────────
    logger.info(f"Finding file: {file_id}")
    logger.info(f"上传目录: {settings.UPLOAD_DIR}")

    # 列出目录下所有文件（调试用）
    all_files = list(settings.UPLOAD_DIR.glob("*"))
    logger.info(f"目录下所有文件: {[f.name for f in all_files]}")

    files = list(settings.UPLOAD_DIR.glob(f"{file_id}_*"))
    logger.info(f"匹配到的文件: {[f.name for f in files]}")

    if not files:
        return error(f"文件不存在，请检查file_id: {file_id}", code=404)

    pdf_path = str(files[0])
    logger.info(f"Starting extraction: {files[0].name}")

    try:
        result = service.extract_from_pdf(
            pdf_path=pdf_path,
            pages=pages,
            max_workers=max_workers
        )

        if result.status == "success":
            logger.info(f"Extraction success: {result.total_params} params")
            return success(
                data={
                    "chip_name": result.chip_name,
                    "chip_type": result.chip_type,
                    "test_scenario": result.test_scenario,
                    "pin_count": len(result.pin_definitions),
                    "statistics": {
                        "total": result.total_params,
                        "A_class": result.a_params,
                        "B_class": result.b_params,
                        "C_class": result.c_params,
                        "blocked": result.blocked_params,
                        "dc_items": result.dc_test_items,
                        "ac_items": result.ac_test_items,
                        "ldo_items": result.ldo_test_items,
                    },
                    "files": {
                        "excel": f"/api/v1/testplan/download/{file_id}/excel",
                        "json": f"/api/v1/testplan/download/{file_id}/json",
                    },
                    "sts_compatibility": result.sts_compatibility,
                    "warnings": result.warnings[:5],
                    "range_recommendations": [
                        rec if isinstance(rec, dict) else rec.model_dump()
                        for rec in result.range_recommendations
                    ],
                    "pin_definitions": [
                        p if isinstance(p, dict) else p.model_dump()
                        for p in result.pin_definitions[:50]
                    ],
                },
                message="提取完成"
            )
        else:
            logger.error(f"Extraction failed: {result.errors}")
            return error(
                message=f"提取失败: {'; '.join(result.errors)}",
                code=500
            )

    except Exception as e:
        logger.error(f"Extraction error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return error(f"提取过程出错: {str(e)}", code=500)

# ============================================================
# 异步提取
# ============================================================

@router.post("/extract-async", summary="提取TestPlan（异步）")
async def extract_testplan_async(
    file_id:     str           = Query(...),
    pages:       Optional[str] = Query(None),
    max_workers: int           = Query(3, ge=1, le=10),
    background_tasks: BackgroundTasks = None
):
    """
    异步提取TestPlan（适合大文件）

    **流程：**
    1. 提交任务 → 返回task_id
    2. 轮询 GET /status/{task_id}
    3. status=completed 时下载文件
    """
    # 验证文件
    files = list(settings.UPLOAD_DIR.glob(f"{file_id}_*"))
    if not files:
        return error(f"文件不存在: {file_id}", code=404)

    # 生成任务ID
    task_id = str(uuid.uuid4())[:8]

    # 初始化任务状态
    task_status[task_id] = {
        "status":     "pending",
        "progress":   0,
        "message":    "任务已创建，等待执行...",
        "file_id":    file_id,
        "start_time": datetime.now().isoformat(),
        "result":     None
    }

    # 提交后台任务
    background_tasks.add_task(
        _run_extract_task,
        task_id     = task_id,
        pdf_path    = str(files[0]),
        pages       = pages,
        max_workers = max_workers
    )

    logger.info(f"Async task submitted: {task_id}")

    return success(
        data={
            "task_id":    task_id,
            "status_url": f"/api/v1/testplan/status/{task_id}",
            "file_id":    file_id,
        },
        message="任务已提交，正在后台处理"
    )


def _run_extract_task(
    task_id:     str,
    pdf_path:    str,
    pages:       Optional[str],
    max_workers: int
) -> None:
    """后台提取任务"""
    try:
        # 更新状态：处理中
        task_status[task_id].update({
            "status":   "processing",
            "progress": 5,
            "message":  "正在准备提取环境..."
        })

        def _progress_cb(current: int, total: int):
            # 这里的 current/total 是由 service 传入的 (例如 1/20, 2/20 ...)
            new_prog = int((current / total) * 100)
            task_status[task_id]["progress"] = new_prog
            
            # 根据进度显示不同消息
            if new_prog < 10:
                msg = "正在解析 PDF 结构..."
            elif new_prog < 20:
                msg = "正在识别芯片类型与提取场景..."
            elif new_prog < 95:
                msg = f"AI 正在并发深度分析中 (进度 {new_prog}%)..."
            else:
                msg = "正在导出结果并生成报告..."
            
            task_status[task_id]["message"] = msg

        result = service.extract_from_pdf(pdf_path, pages, max_workers, progress_callback=_progress_cb)

        if result.status == "success":
            task_status[task_id] = {
                "status":   "completed",
                "progress": 100,
                "message":  "提取完成",
                "end_time": datetime.now().isoformat(),
                "result": {
                    "chip_name": result.chip_name,
                    "chip_type": result.chip_type,
                    "test_scenario": result.test_scenario,
                    "pin_count": len(result.pin_definitions),
                    "statistics": {
                        "total": result.total_params,
                        "A_class": result.a_params,
                        "B_class": result.b_params,
                        "C_class": result.c_params,
                        "blocked": result.blocked_params,
                        "dc_items": result.dc_test_items,
                        "ac_items": result.ac_test_items,
                        "ldo_items": result.ldo_test_items,
                    },
                    "files": {
                        "excel": f"/api/v1/testplan/download/{task_status[task_id]['file_id']}/excel",
                        "json": f"/api/v1/testplan/download/{task_status[task_id]['file_id']}/json",
                    },
                    "sts_compatibility": result.sts_compatibility,
                    "warnings": result.warnings[:5],
                    "range_recommendations": [
                        rec if isinstance(rec, dict) else rec.model_dump()
                        for rec in result.range_recommendations
                    ],
                    "pin_definitions": [
                        p if isinstance(p, dict) else p.model_dump()
                        for p in result.pin_definitions[:50]
                    ],
                }
            }

        else:
            task_status[task_id].update({
                "status":   "failed",
                "progress": 0,
                "message":  f"提取失败: {'; '.join(result.errors)}",
                "end_time": datetime.now().isoformat(),
            })

    except Exception as e:
        task_status[task_id].update({
            "status":   "failed",
            "progress": 0,
            "message":  f"任务出错: {str(e)}",
            "end_time": datetime.now().isoformat(),
        })


# ============================================================
# 任务状态查询
# ============================================================

@router.get("/status/{task_id}", summary="查询任务状态")
async def get_task_status(task_id: str):
    """
    查询异步任务状态

    **status说明：**
    - pending   : 等待执行
    - processing: 处理中
    - completed : 完成
    - failed    : 失败
    """
    if task_id not in task_status:
        return error(f"任务不存在: {task_id}", code=404)

    task = task_status[task_id]

    return success(
        data={
            "task_id":  task_id,
            "status":   task["status"],
            "progress": task.get("progress", 0),
            "message":  task.get("message", ""),
            "result":   task.get("result"),
            "start_time": task.get("start_time"),
            "end_time":   task.get("end_time"),
        },
        message="查询成功"
    )


# ============================================================
# 文件下载
# ============================================================

@router.get("/download/{file_id}/{file_type}", summary="下载结果文件")
async def download_file(
    file_id:   str,
    file_type: str
):
    """
    下载生成的文件

    - **file_type**: excel 或 json
    """
    if file_type not in ["excel", "json"]:
        return error("file_type必须是excel或json", code=400)

    extension = "xlsx" if file_type == "excel" else "json"

    # 优先用 file_id 精确匹配
    files = list(
        settings.PROCESSED_DIR.glob(f"*{file_id}*TestPlan.{extension}")
    )

    # file_id 匹配不到时，降级到全局最新文件
    if not files:
        logger.warning(
            f"⚠️ 未找到 file_id={file_id} 对应的文件，"
            f"降级为最新文件"
        )
        files = list(
            settings.PROCESSED_DIR.glob(f"*TestPlan.{extension}")
        )

    if not files:
        return error("文件不存在，请先执行提取", code=404)

    # 取最新的文件
    file_path  = sorted(files, key=lambda f: f.stat().st_mtime)[-1]
    media_type = (
        "application/vnd.openxmlformats-officedocument"
        ".spreadsheetml.sheet"
        if file_type == "excel"
        else "application/json"
    )

    logger.info(f"Downloading file: {file_path.name}")

    return FileResponse(
        path       = str(file_path),
        filename   = file_path.name,
        media_type = media_type
    )


# ============================================================
# 参数预览（前端表格展示用）
# ============================================================

@router.get("/preview/{file_id}", summary="预览提取的参数")
async def preview_params(
    file_id:   str,
    page:      int = Query(1,  ge=1,  description="页码"),
    page_size: int = Query(20, ge=5, le=100, description="每页数量"),
    category:  Optional[str] = Query(None, description="筛选类别A/B/C"),
    status:    Optional[str] = Query(None, description="筛选状态")
):
    """
    预览提取的参数列表（分页）

    **前端表格展示使用此接口**

    **参数筛选：**
    - category: A/B/C
    - status  : 待复核/需人工确认/已拦截
    """
    import json

    # 查找JSON文件
    json_files = list(
        settings.PROCESSED_DIR.glob(f"*{file_id}*TestPlan.json")
    )
    if not json_files:
        return error(f"未找到file_id={file_id}的结果", code=404)

    with open(json_files[-1], "r", encoding="utf-8") as f:
        data = json.load(f)

    params = data.get("parameters", [])

    # 筛选
    if category:
        params = [
            p for p in params
            if p.get("category", "").upper() == category.upper()
        ]

    # 分页
    total      = len(params)
    start      = (page - 1) * page_size
    end        = start + page_size
    page_items = params[start:end]

    return paginate(
        items     = page_items,
        total     = total,
        page      = page,
        page_size = page_size,
        message   = "查询成功"
    )


# ============================================================
# 引脚预览（前端引脚表格展示用）
# ============================================================

@router.get("/pins/{file_id}", summary="查看提取的引脚定义")
async def get_pin_definitions(file_id: str):
    """
    获取模块一提取的引脚定义

    **前端引脚表格展示使用此接口**
    **模块二也通过此接口获取引脚信息**
    """
    import json

    json_files = list(
        settings.PROCESSED_DIR.glob(f"*{file_id}*TestPlan.json")
    )
    if not json_files:
        return error(f"未找到file_id={file_id}的结果", code=404)

    with open(json_files[-1], "r", encoding="utf-8") as f:
        data = json.load(f)

    pins      = data.get("pin_definitions", [])
    chip_name = data.get("chip_name", "")
    chip_type = data.get("chip_type", "")

    return success(
        data={
            "chip_name":     chip_name,
            "chip_type":     chip_type,
            "pin_count":     len(pins),
            "pin_definitions": pins,
            "has_pins":      len(pins) > 0,
        },
        message="查询成功" if pins else "未提取到引脚定义"
    )


# ============================================================
# 文件列表（分页）
# ============================================================

@router.get("/list", summary="获取已处理文件列表")
async def list_files(
    page:      int = Query(1,  ge=1),
    page_size: int = Query(10, ge=5, le=50)
):
    """
    获取所有已处理的文件列表（分页）
    """
    excel_files = sorted(
        settings.PROCESSED_DIR.glob("*TestPlan.xlsx"),
        key=lambda f: f.stat().st_ctime,
        reverse=True
    )

    items = []
    for f in excel_files:
        # 找对应的JSON
        json_file = f.with_suffix(".json")
        chip_type = ""
        chip_name = ""

        if json_file.exists():
            try:
                import json
                with open(json_file) as jf:
                    jd = json.load(jf)
                chip_type = jd.get("chip_type", "")
                chip_name = jd.get("chip_name", "")
            except Exception:
                pass

        items.append({
            "filename":    f.name,
            "chip_name":   chip_name,
            "chip_type":   chip_type,
            "size_mb":     round(f.stat().st_size / 1024 / 1024, 2),
            "created_time": datetime.fromtimestamp(
                f.stat().st_ctime
            ).strftime("%Y-%m-%d %H:%M:%S"),
        })

    total      = len(items)
    start      = (page - 1) * page_size
    page_items = items[start: start + page_size]

    return paginate(
        items     = page_items,
        total     = total,
        page      = page,
        page_size = page_size
    )


# ============================================================
# 清理旧文件
# ============================================================

@router.delete("/clean", summary="清理旧文件")
async def clean_old_files(
    keep_days: int = Query(7, ge=1, description="保留最近N天的文件")
):
    """清理旧文件"""
    import time

    current_time  = time.time()
    deleted_count = 0

    for directory in [settings.UPLOAD_DIR, settings.PROCESSED_DIR]:
        for f in directory.glob("*"):
            if current_time - f.stat().st_mtime > keep_days * 86400:
                f.unlink()
                deleted_count += 1

    logger.info(f"清理了 {deleted_count} 个旧文件")

    return success(
        data={"deleted_count": deleted_count},
        message=f"已清理 {deleted_count} 个文件"
    )
# ============================================================
# 诊断接口（调试用）
# ============================================================

@router.get("/test-api", summary="测试DeepSeek连通性")
async def test_api_connection():
    """直接在FastAPI进程内测试DeepSeek连通性"""
    import os
    import sys
    import httpx
    from openai import OpenAI

    results = {
        "python":      sys.executable,
        "https_proxy": os.environ.get("HTTPS_PROXY", "未设置"),
        "http_proxy":  os.environ.get("HTTP_PROXY",  "未设置"),
        "api_key":     (
            settings.DEEPSEEK_API_KEY[:8] + "..."
            if settings.DEEPSEEK_API_KEY else "未配置"
        ),
        "base_url":    settings.DEEPSEEK_BASE_URL,
    }

    # 测试1：httpx直连
    try:
        resp = httpx.get(
            "https://api.deepseek.com",
            timeout=10.0
        )
        results["httpx_test"] = f"Success: {resp.status_code}"
    except Exception as e:
        results["httpx_test"] = f"Failed: {type(e).__name__}: {str(e)[:200]}"

    # 测试2：OpenAI客户端直接调用
    try:
        client = OpenAI(
            api_key  = settings.DEEPSEEK_API_KEY,
            base_url = settings.DEEPSEEK_BASE_URL,
        )
        resp = client.chat.completions.create(
            model    = settings.DEEPSEEK_MODEL,
            messages = [{"role": "user", "content": "回复OK两个字"}],
            max_tokens = 5
        )
        results["openai_test"] = f"Success: {resp.choices[0].message.content}"
    except Exception as e:
        results["openai_test"] = f"Failed: {type(e).__name__}: {str(e)[:200]}"

    # 测试3：instructor客户端
    try:
        import instructor
        iclient = instructor.from_openai(
            OpenAI(
                api_key  = settings.DEEPSEEK_API_KEY,
                base_url = settings.DEEPSEEK_BASE_URL,
            )
        )
        from app.models.testplan import TestPlan
        resp2 = iclient.chat.completions.create(
            model          = settings.DEEPSEEK_MODEL,
            messages       = [{"role": "user", "content": "返回一个空的测试计划"}],
            response_model = TestPlan,
            max_retries    = 1,
            max_tokens     = settings.MAX_TOKENS,
        )
        results["instructor_test"] = f"Success: chip_type={resp2.chip_type}"
    except Exception as e:
        results["instructor_test"] = f"Failed: {type(e).__name__}: {str(e)[:200]}"

    return success(data=results, message="诊断完成")
from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import (
    agent_runs,
    chat,
    codegen,
    diagnosis,
    rag,
    resource_map,
    testplan,
    testprogram,
    workspace_memory,
)
from app.core.config import BASE_DIR, get_settings
from app.core.response import success
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()
settings.create_dirs()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import os

    if settings.CLEAR_PROXY_ENV:
        for proxy_var in [
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "http_proxy",
            "https_proxy",
            "ALL_PROXY",
            "all_proxy",
        ]:
            if proxy_var in os.environ:
                logger.info(f"Cleanup proxy env: {proxy_var}")
                del os.environ[proxy_var]

    logger.info(f"START {settings.PROJECT_NAME} v{settings.VERSION} starting")
    settings.create_dirs()
    logger.info("OK: Data directories created")
    logger.info(f"DIR: Upload dir: {settings.UPLOAD_DIR}")
    logger.info(f"DIR: Processed dir: {settings.PROCESSED_DIR}")
    logger.info(f"DIR: Upload dir exists: {settings.UPLOAD_DIR.exists()}")
    logger.info(f"FILE: .env path: {BASE_DIR / 'backend' / '.env'}")
    logger.info(f"FILE: .env exists: {(BASE_DIR / 'backend' / '.env').exists()}")

    if settings.DEEPSEEK_API_KEY:
        logger.info(f"OK: DeepSeek API configured: {settings.DEEPSEEK_API_KEY[:8]}...")
    else:
        logger.warning("WARN: DeepSeek API not configured")
        logger.warning(f"WARN: Please check .env file: {BASE_DIR / 'backend' / '.env'}")

    logger.info("INFO: Local access: http://localhost:8000/docs")
    logger.info("INFO: LAN access: http://0.0.0.0:8000/docs")

    try:
        from app.services.rag_service import STS8200S_BUILTIN_KNOWLEDGE, get_rag_service

        rag_svc = get_rag_service()
        if not rag_svc.is_ready:
            logger.info("Initializing built-in RAG knowledge base")
            rag_svc.build_index_from_text(STS8200S_BUILTIN_KNOWLEDGE)
            logger.info(f"RAG ready: {rag_svc.status['doc_count']} chunks")
        else:
            logger.info(f"RAG already loaded: {rag_svc.status['doc_count']} chunks")
    except Exception as rag_exc:
        logger.warning(f"RAG initialization skipped: {rag_exc}")

    yield
    logger.info("Application shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
## 基于大模型的智能 ATE 开发平台
### 模块 1：Datasheet / TestPlan 自动提取
### 模块 2：STS8200S 资源映射与原理图辅助设计
### 模块 3：RAG 测试代码生成与工程包整理
### 模块 4：轻量化良率诊断与工程师助手
""",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=settings.ALLOWED_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Type", "Content-Length"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    client_host = request.client.host if request.client else "unknown"
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        f"HTTP {request.method} {request.url.path} "
        f"status={response.status_code} duration={duration:.3f}s client={client_host}"
    )
    return response


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "code": 404,
            "status": "error",
            "message": f"接口不存在: {request.url.path}",
            "data": None,
            "timestamp": int(time.time()),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc):
    logger.error(f"Unhandled exception: {exc}")
    import traceback

    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "status": "error",
            "message": str(exc) if settings.DEBUG else "服务器错误",
            "data": None,
            "timestamp": int(time.time()),
        },
    )


app.include_router(testplan.router, prefix="/api/v1/testplan", tags=["模块 1 - TestPlan 提取"])
app.include_router(resource_map.router, prefix="/api/v1/resource-map", tags=["模块 2 - 资源映射"])
app.include_router(codegen.router, prefix="/api/v1/codegen", tags=["模块 3 - 代码生成"])
app.include_router(agent_runs.router, prefix="/api/v1/agent-runs", tags=["统一 Agent Runs"])
app.include_router(testprogram.router, prefix="/api/v1/testprogram", tags=["模块 3 - 工程包导出"])
app.include_router(rag.router, prefix="/api/v1/rag", tags=["RAG 检索增强"])
app.include_router(diagnosis.router, prefix="/api/v1/diagnosis", tags=["模块 4 - 良率诊断"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["工程师助手"])
app.include_router(workspace_memory.router, prefix="/api/v1/workspace-memory", tags=["Workspace Memory"])

app.mount("/files", StaticFiles(directory=str(settings.PROCESSED_DIR)), name="files")


@app.get("/", tags=["系统"], summary="系统信息")
async def root():
    return success(
        data={
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status": "running",
            "docs": "/docs",
            "modules": {
                "module_1": "TestPlan extraction OK",
                "module_2": "Resource mapping OK",
                "module_3": "AI code generation OK",
                "engineer_assistant": "Workspace-aware copilot OK",
            },
        },
        message="服务运行正常",
    )


@app.get("/health", tags=["系统"], summary="健康检查")
async def health_check():
    return success(
        data={
            "status": "healthy",
            "version": settings.VERSION,
            "debug_mode": settings.DEBUG,
            "api_configured": bool(settings.DEEPSEEK_API_KEY),
            "upload_dir": str(settings.UPLOAD_DIR),
            "upload_exists": settings.UPLOAD_DIR.exists(),
            "allowed_origins": settings.ALLOWED_ORIGINS,
            "ssl_verify": settings.SSL_VERIFY,
            "ocr_fallback_enabled": settings.ENABLE_PDF_OCR_FALLBACK,
        },
        message="服务健康",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info",
    )

# app/main.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time

from app.core.config import get_settings, BASE_DIR
from app.core.response import success, error
from app.api.v1 import testplan, resource_map, codegen, rag, diagnosis
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()

# Ensure data directories exist before static mounts are evaluated.
settings.create_dirs()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    import os

    # ← 新增：启动时清除代理环境变量
    for proxy_var in [
        "HTTP_PROXY", "HTTPS_PROXY",
        "http_proxy", "https_proxy",
        "ALL_PROXY", "all_proxy"
    ]:
        if proxy_var in os.environ:
            logger.info(f" 清除代理: {proxy_var}={os.environ[proxy_var]}")
            del os.environ[proxy_var]
    print("\n" + "=" * 60)
    print(f"START {settings.PROJECT_NAME} v{settings.VERSION} starting...")
    print("=" * 60)

    # 创建目录
    settings.create_dirs()
    logger.info("OK: Data directories created")

    # 打印关键路径配置（调试用）
    logger.info(f"DIR: Upload dir: {settings.UPLOAD_DIR}")
    logger.info(f"DIR: Processed dir: {settings.PROCESSED_DIR}")
    logger.info(f"DIR: Upload dir exists: {settings.UPLOAD_DIR.exists()}")
    logger.info(f"FILE: .env path: {BASE_DIR / 'backend' / '.env'}")
    logger.info(f"FILE: .env exists: {(BASE_DIR / 'backend' / '.env').exists()}")

    # 验证API Key
    if settings.DEEPSEEK_API_KEY:
        logger.info(
            f"OK: DeepSeek API configured: "
            f"{settings.DEEPSEEK_API_KEY[:8]}..."
        )
    else:
        logger.warning("WARN: DeepSeek API not configured! Extraction will not work!")
        logger.warning(
            f"WARN: Please check .env file: "
            f"{BASE_DIR / 'backend' / '.env'}"
        )

    print(f"INFO: Local access: http://localhost:8000/docs")
    print(f"INFO: LAN access: http://0.0.0.0:8000/docs")
    print("=" * 60 + "\n")

    # ── 启动时自动初始化 RAG 内置知识库 ─────────────────────────
    try:
        from app.services.rag_service import get_rag_service, STS8200S_BUILTIN_KNOWLEDGE
        rag_svc = get_rag_service()
        if not rag_svc.is_ready:
            logger.info(" 初始化 RAG 内置知识库...")
            rag_svc.build_index_from_text(STS8200S_BUILTIN_KNOWLEDGE)
            logger.info(f"✅ RAG 知识库就绪: {rag_svc.status['doc_count']} 个片段")
        else:
            logger.info(f" RAG 索引已加载: {rag_svc.status['doc_count']} 个片段")
    except Exception as rag_e:
        logger.warning(f"RAG 初始化跳过（不影响其他功能）: {rag_e}")


    yield

    logger.info(" 应用关闭")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="""
##  基于语言大模型的智能ATE测试开发平台

### 模块①：TestPlan 自动提取 + AI 量程推荐 ✅
### 模块②：资源映射与原理图辅助设计 ✅
### 模块③：RAG 测试代码生成 + 静态预校验 ✅
### 模块④：边缘 AI 良率诊断 ✅
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# ── CORS配置 ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "Content-Disposition",
        "Content-Type",
        "Content-Length",
    ]
)


# ── 请求日志中间件 ────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有请求的耗时"""
    start_time = time.time()
    print(f"\n{'=' * 60}")
    print(f"REQ: {request.method} {request.url.path}")
    print(f"   From: {request.client.host}")

    response = await call_next(request)
    duration = time.time() - start_time

    print(f"RES: {response.status_code} ({duration:.3f}s)")
    print(f"{'=' * 60}\n")

    return response


# ── 统一异常处理 ──────────────────────────────────────────────
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "code": 404,
            "status": "error",
            "message": f"接口不存在: {request.url.path}",
            "data": None,
            "timestamp": int(time.time())
        }
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
            "timestamp": int(time.time())
        }
    )


# ── 注册路由 ──────────────────────────────────────────────────
app.include_router(
    testplan.router,
    prefix="/api/v1/testplan",
    tags=["模块① TestPlan提取"]
)

app.include_router(
    resource_map.router,
    prefix="/api/v1/resource-map",
    tags=["模块② 资源映射"]
)

app.include_router(
    codegen.router,
    prefix="/api/v1/codegen",
    tags=["模块③ 测试代码生成"]
)

app.include_router(
    rag.router,
    prefix="/api/v1/rag",
    tags=["模块③ RAG 检索增强"]
)

app.include_router(
    diagnosis.router,
    prefix="/api/v1/diagnosis",
    tags=["模块④ 良率诊断"]
)

# ── 静态文件 ──────────────────────────────────────────────────
app.mount(
    "/files",
    StaticFiles(directory=str(settings.PROCESSED_DIR)),
    name="files"
)


# ── 系统接口 ──────────────────────────────────────────────────
@app.get("/", tags=["系统"], summary="系统信息")
async def root():
    """获取系统基本信息"""
    return success(
        data={
            "name":    settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status":  "running",
            "docs":    "/docs",
            "modules": {
                "module_1": "TestPlan extraction OK",
                "module_2": "Resource mapping OK",
                "module_3": "AI code generation OK"
            }
        },
        message="服务运行正常"
    )


@app.get("/health", tags=["系统"], summary="健康检查")
async def health_check():
    """健康检查"""
    return success(
        data={
            "status":         "healthy",
            "version":        settings.VERSION,
            "debug_mode":     settings.DEBUG,
            "api_configured": bool(settings.DEEPSEEK_API_KEY),
            "upload_dir":     str(settings.UPLOAD_DIR),
            "upload_exists":  settings.UPLOAD_DIR.exists(),
        },
        message="服务健康"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )

"""
RAG API - 模块三扩展
管理 STS8200S 手册向量索引的构建与查询
"""
from fastapi import APIRouter, Body
from typing import Optional
from pydantic import BaseModel, Field

from app.services.rag_service import get_rag_service, STS8200S_BUILTIN_KNOWLEDGE
from app.core.response import success, error
from app.core.config import get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger   = setup_logger()
router   = APIRouter()


class BuildRequest(BaseModel):
    pdf_path: Optional[str] = Field(None, description="STS8200S 手册 PDF 路径（留空使用内置知识库）")

class QueryRequest(BaseModel):
    query: str  = Field(..., description="自然语言查询")
    top_k: int  = Field(5, ge=1, le=20)


@router.post("/build", summary="构建 RAG 手册索引")
async def build_index(req: BuildRequest = Body(...)):
    """
    构建 STS8200S 编程手册向量索引。
    - 若提供 pdf_path：解析 PDF 建立向量索引
    - 若不提供：使用内置 STS8200S 知识库（7 大核心 API 章节）
    """
    svc = get_rag_service()
    try:
        if req.pdf_path:
            result = svc.build_index(req.pdf_path)
            msg = f"PDF 索引构建完成，共 {result['chunks']} 个片段"
        else:
            # 使用内置知识库
            result = svc.build_index_from_text(STS8200S_BUILTIN_KNOWLEDGE)
            msg = f"内置知识库索引完成，共 {result['chunks']} 个片段"

        return success(data={**result, **svc.status}, message=msg)
    except Exception as e:
        logger.error(f"RAG 索引构建失败: {e}")
        return error(f"索引构建失败: {str(e)}", code=500)


@router.get("/status", summary="查询 RAG 索引状态")
async def get_status():
    """查询当前 RAG 系统是否就绪及索引规模"""
    svc = get_rag_service()
    return success(data=svc.status, message="查询成功")


@router.post("/query", summary="检索手册相关片段（调试用）")
async def query_manual(req: QueryRequest = Body(...)):
    """检索 STS8200S 手册中与查询最相关的片段"""
    svc = get_rag_service()
    if not svc.is_ready:
        return error("RAG 索引尚未建立，请先调用 /build", code=503)
    chunks = svc.retrieve(req.query, top_k=req.top_k)
    return success(data={"query": req.query, "results": chunks}, message=f"检索到 {len(chunks)} 个片段")

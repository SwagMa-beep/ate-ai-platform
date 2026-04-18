"""
统一响应格式
所有API接口统一使用此格式返回
前端只需处理一种格式
"""
from fastapi.responses import JSONResponse
from typing import Any, Optional
import time


def success(
    data: Any = None,
    message: str = "操作成功",
    code: int = 200
) -> JSONResponse:
    """
    成功响应

    Args:
        data   : 返回数据
        message: 提示信息
        code   : 状态码

    Returns:
        {
            "code": 200,
            "status": "success",
            "message": "操作成功",
            "data": {...},
            "timestamp": 1234567890
        }
    """
    return JSONResponse(
        status_code=code,
        content={
            "code":      code,
            "status":    "success",
            "message":   message,
            "data":      data,
            "timestamp": int(time.time())
        }
    )


def error(
    message: str = "操作失败",
    code: int = 400,
    data: Any = None
) -> JSONResponse:
    """
    错误响应

    Args:
        message: 错误信息
        code   : 状态码
        data   : 附加数据（可选）

    Returns:
        {
            "code": 400,
            "status": "error",
            "message": "错误信息",
            "data": null,
            "timestamp": 1234567890
        }
    """
    return JSONResponse(
        status_code=code,
        content={
            "code":      code,
            "status":    "error",
            "message":   message,
            "data":      data,
            "timestamp": int(time.time())
        }
    )


def paginate(
    items: list,
    total: int,
    page: int,
    page_size: int,
    message: str = "查询成功"
) -> JSONResponse:
    """
    分页响应

    Returns:
        {
            "code": 200,
            "status": "success",
            "message": "查询成功",
            "data": {
                "items": [...],
                "total": 100,
                "page": 1,
                "page_size": 10,
                "total_pages": 10,
                "has_next": true,
                "has_prev": false
            }
        }
    """
    total_pages = (total + page_size - 1) // page_size

    return JSONResponse(
        status_code=200,
        content={
            "code":    200,
            "status":  "success",
            "message": message,
            "data": {
                "items":       items,
                "total":       total,
                "page":        page,
                "page_size":   page_size,
                "total_pages": total_pages,
                "has_next":    page < total_pages,
                "has_prev":    page > 1,
            },
            "timestamp": int(time.time())
        }
    )
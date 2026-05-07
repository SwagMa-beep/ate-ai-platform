"""Unified engineer assistant chat API."""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.core.response import error, success
from app.services.chat_service import get_engineer_assistant_chat_service

router = APIRouter()
service = get_engineer_assistant_chat_service()


class ChatQueryRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message")
    mode: Literal["general", "testplan", "resource-map", "codegen", "diagnosis", "run-analysis"] = Field(
        "general",
        description="Assistant mode",
    )
    run_id: Optional[str] = Field(None, description="Optional selected run id")


@router.post("/query", summary="Query the engineer assistant")
async def query_engineer_assistant(req: ChatQueryRequest):
    try:
        result = service.answer(message=req.message, mode=req.mode, run_id=req.run_id)
        return success(data=result, message="Engineer assistant response ready")
    except ValueError as exc:
        return error(str(exc), code=400)
    except Exception as exc:
        return error(f"Engineer assistant failed: {exc}", code=500)


@router.post("/message", summary="Send engineer assistant message with optional images")
async def send_engineer_assistant_message(
    message: str = Form(""),
    mode: Literal["general", "testplan", "resource-map", "codegen", "diagnosis", "run-analysis"] = Form("general"),
    run_id: Optional[str] = Form(None),
    images: list[UploadFile] = File(default=[]),
):
    try:
        result = await service.answer_message(
            message=message,
            mode=mode,
            run_id=run_id,
            images=images or [],
        )
        return success(data=result, message="Engineer assistant response ready")
    except ValueError as exc:
        return error(str(exc), code=400)
    except Exception as exc:
        return error(f"Engineer assistant failed: {exc}", code=500)

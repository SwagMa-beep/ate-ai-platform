"""Workspace memory endpoints for the unified engineer assistant."""

from fastapi import APIRouter

from app.core.response import success
from app.services.workspace_memory_service import get_workspace_memory_service

router = APIRouter()
service = get_workspace_memory_service()


@router.get("", summary="Get workspace memory")
async def get_workspace_memory():
    return success(data=service.load_memory(), message="Workspace memory loaded")


@router.post("/reset", summary="Reset workspace memory")
async def reset_workspace_memory():
    return success(data=service.reset_memory(), message="Workspace memory reset")

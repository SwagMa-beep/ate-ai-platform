"""Unified engineer assistant service with optional multimodal image support."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import UploadFile
from openai import OpenAI

from app.core.config import BASE_DIR, get_settings
from app.services.rag_service import get_rag_service
from app.services.run_store import get_run_store
from app.services.workspace_memory_service import get_workspace_memory_service
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()

MAX_IMAGES = 5
MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}

MODE_GUIDANCE = {
    "testplan": "Focus on datasheet extraction quality, missing parameters, test conditions, pin definitions, and review risks.",
    "resource-map": "Focus on STS8200S resource allocation, power rails, PGS consistency, dual-site risks, and adapter mapping logic.",
    "codegen": "Focus on code skeleton feasibility, platform API usage, static validation, compile risks, and next coding actions.",
    "diagnosis": "Focus on failure symptoms, waveform interpretation, likely root causes, and suggested debug checks.",
    "run-analysis": "Focus on the current or recent agent run, step status, warnings, human review state, and the next best action.",
    "general": "Act as a senior ATE engineering copilot and coordinate across extraction, mapping, codegen, review, and diagnosis.",
}


class EngineerAssistantChatService:
    def __init__(self) -> None:
        self.memory = get_workspace_memory_service()
        self.run_store = get_run_store()
        self.rag = get_rag_service()
        self.knowledge_root = BASE_DIR / "data" / "knowledge"
        self._text_client: Optional[OpenAI] = None
        self._vision_client: Optional[OpenAI] = None

    def answer(self, *, message: str, mode: str = "general", run_id: Optional[str] = None) -> dict[str, Any]:
        return self.answer_message(message=message, mode=mode, run_id=run_id, images=[])

    async def answer_message(
        self,
        *,
        message: str,
        mode: str = "general",
        run_id: Optional[str] = None,
        images: list[UploadFile],
    ) -> dict[str, Any]:
        clean_message = str(message or "").strip()
        if not clean_message and not images:
            raise ValueError("Message or images must be provided.")

        normalized_mode = mode if mode in MODE_GUIDANCE else "general"
        image_payloads = await self._prepare_images(images or [])
        workspace_context = self.memory.build_context_summary()
        run_context = self._build_run_context(run_id, normalized_mode)
        memory_snapshot = self.memory.load_memory()
        chip = memory_snapshot.get("current_chip") or {}
        chip_name = str(chip.get("name") or "").strip() or None
        chip_type = str(chip.get("chip_type") or "").strip() or None

        retrieved_chunks = self._retrieve_context_chunks(
            message=clean_message,
            mode=normalized_mode,
            chip_name=chip_name,
            chip_type=chip_type,
        )

        prompt = self._build_prompt(
            message=clean_message or "请先观察我上传的图片，再给出工程分析和下一步建议。",
            mode=normalized_mode,
            workspace_context=workspace_context,
            run_context=run_context["summary"],
            retrieved_chunks=retrieved_chunks,
            has_images=bool(image_payloads),
        )

        answer_text = await self._generate_answer(
            prompt,
            image_payloads=image_payloads,
            fallback_context=workspace_context or run_context["summary"],
        )
        if clean_message:
            self.memory.add_note(f"{normalized_mode}: {clean_message}")

        return {
            "mode": normalized_mode,
            "answer": answer_text,
            "context_summary": workspace_context,
            "related_run": run_context["run"],
            "retrieved_chunks": [
                {
                    "source": chunk.get("source", ""),
                    "score": chunk.get("score", 0),
                    "text": str(chunk.get("text", ""))[:300],
                }
                for chunk in retrieved_chunks[:3]
            ],
            "suggested_actions": self._build_suggested_actions(normalized_mode, run_context["run"]),
            "image_count": len(image_payloads),
            "model_backend": "vision" if image_payloads else settings.get_text_backend(),
        }

    def _retrieve_context_chunks(
        self,
        *,
        message: str,
        mode: str,
        chip_name: Optional[str],
        chip_type: Optional[str],
    ) -> list[dict[str, Any]]:
        retrieved_chunks: list[dict[str, Any]] = []
        if message and self.rag.is_ready:
            try:
                retrieved_chunks = self.rag.retrieve(
                    message,
                    chip_name=chip_name,
                    chip_type=chip_type,
                )
            except Exception as exc:
                logger.warning(f"Engineer assistant RAG retrieve failed: {exc}")

        local_chunks = self._retrieve_local_knowledge(
            message or f"{chip_name or ''} {chip_type or ''}",
            mode=mode,
            chip_name=chip_name,
            chip_type=chip_type,
        )
        if local_chunks:
            retrieved_chunks.extend(local_chunks)
            retrieved_chunks = retrieved_chunks[:5]
        return retrieved_chunks

    def _retrieve_local_knowledge(
        self,
        message: str,
        *,
        mode: str,
        chip_name: Optional[str],
        chip_type: Optional[str],
    ) -> list[dict[str, Any]]:
        if not self.knowledge_root.exists():
            return []

        folders = ["chips", "sts8200s", "standards"]
        if mode == "testplan":
            folders.append("testplan")
        elif mode == "resource-map":
            folders.append("resource")
        elif mode == "codegen":
            folders.append("codegen")
        elif mode == "diagnosis":
            folders.append("failure")

        tokens = {
            token.lower()
            for token in re.findall(r"[A-Za-z0-9_+\-]{3,}", f"{message} {chip_name or ''} {chip_type or ''}")
            if token
        }
        results: list[dict[str, Any]] = []
        for folder in folders:
            root = self.knowledge_root / folder
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.suffix.lower() not in {".md", ".txt", ".json"}:
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                haystack = f"{path.name.lower()} {text.lower()}"
                score = sum(1 for token in tokens if token in haystack)
                if score <= 0 and folder not in {"sts8200s", "standards"}:
                    continue
                snippet = re.sub(r"\s+", " ", text).strip()[:360]
                if not snippet:
                    continue
                results.append(
                    {
                        "source": f"knowledge/{folder}/{path.name}",
                        "score": float(score),
                        "text": snippet,
                    }
                )
        results.sort(key=lambda item: item.get("score", 0), reverse=True)
        return results[:2]

    def _build_run_context(self, run_id: Optional[str], mode: str) -> dict[str, Any]:
        run = self.run_store.get_run(run_id) if run_id else None
        if run is None and mode == "run-analysis":
            latest = self.run_store.list_runs(limit=1)
            run = latest[0] if latest else None
        if run is None:
            latest = self.run_store.list_runs(limit=1)
            run = latest[0] if latest else None

        if not run:
            return {"run": None, "summary": ""}

        steps = run.get("steps") or []
        latest_step = steps[-1] if steps else {}
        warnings = run.get("warnings") or []
        errors = run.get("errors") or []
        summary_lines = [
            "[最近运行上下文]",
            f"- Run: {run.get('run_id', '')}",
            f"- Flow: {run.get('flow_name', '')}",
            f"- Status: {run.get('status', '')}",
        ]
        if latest_step:
            summary_lines.append(
                f"- Latest step: {latest_step.get('agent', '')} / {latest_step.get('status', '')} / {latest_step.get('message', '')}"
            )
        if warnings:
            summary_lines.append(f"- Warnings: {'; '.join(str(item) for item in warnings[:3])}")
        if errors:
            summary_lines.append(f"- Errors: {'; '.join(str(item) for item in errors[:3])}")
        return {"run": run, "summary": "\n".join(summary_lines)}

    def _build_prompt(
        self,
        *,
        message: str,
        mode: str,
        workspace_context: str,
        run_context: str,
        retrieved_chunks: list[dict[str, Any]],
        has_images: bool,
    ) -> str:
        rag_context = "\n\n".join(
            f"[{chunk.get('source', 'RAG')} | score={chunk.get('score', 0)}]\n{chunk.get('text', '')}"
            for chunk in retrieved_chunks[:3]
        )
        image_note = (
            "\n[Image analysis rule]\n"
            "If images are provided, first describe what is observed, then explain the likely engineering meaning, then suggest next actions.\n"
            if has_images
            else ""
        )
        return f"""You are the engineer assistant inside an ATE AI platform.

[Assistant mode]
{mode}

[Mode guidance]
{MODE_GUIDANCE.get(mode, MODE_GUIDANCE['general'])}

[Workspace context]
{workspace_context or "(No workspace memory recorded yet.)"}

[Run context]
{run_context or "(No recent run context available.)"}

[RAG context]
{rag_context or "(No RAG context available.)"}
{image_note}
[User request]
{message}

[Response requirements]
1. Answer in concise Simplified Chinese.
2. Be specific and engineering-oriented.
3. If a risk or uncertainty exists, say it clearly.
4. Prefer next-step guidance over generic theory.
5. Do not claim the platform can do real bench execution unless the context explicitly supports it.
"""

    async def _generate_answer(
        self,
        prompt: str,
        *,
        image_payloads: list[dict[str, str]],
        fallback_context: str,
    ) -> str:
        if image_payloads:
            if not settings.has_vision_model():
                return "当前主框架还没有配置视觉模型，暂时无法分析图片。请先在后端 `.env` 配置 `VISION_API_KEY`、`VISION_BASE_URL` 和 `VISION_MODEL`。"
            client = self._get_vision_client()
            content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
            for image in image_payloads:
                content.append({"type": "image_url", "image_url": {"url": image["data_url"]}})
            response = client.chat.completions.create(
                model=settings.VISION_MODEL,
                messages=[{"role": "user", "content": content}],
                temperature=0.2,
                max_tokens=min(settings.MAX_TOKENS, 1500),
            )
            return (response.choices[0].message.content or "").strip()

        if not settings.get_text_api_key():
            return (
                "当前未配置文本模型 API，工程师助手先退回上下文摘要模式。\n\n"
                f"{fallback_context or '当前还没有可用的工作区上下文，请先执行一次 TestPlan、资源映射或代码生成。'}"
            )

        client = self._get_text_client()
        response = client.chat.completions.create(
            model=settings.get_text_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=min(settings.MAX_TOKENS, 1200),
        )
        return (response.choices[0].message.content or "").strip()

    async def _prepare_images(self, images: list[UploadFile]) -> list[dict[str, str]]:
        if len(images) > MAX_IMAGES:
            raise ValueError(f"At most {MAX_IMAGES} images are allowed.")

        payloads: list[dict[str, str]] = []
        for image in images:
            content_type = (image.content_type or "").lower()
            filename = image.filename or "image"
            suffix = Path(filename).suffix.lower()
            if content_type not in ALLOWED_IMAGE_TYPES or suffix not in ALLOWED_IMAGE_EXTS:
                raise ValueError("Only PNG, JPG, JPEG, and WEBP images are supported.")
            content = await image.read()
            if not content:
                raise ValueError(f"Image {filename} is empty.")
            if len(content) > MAX_IMAGE_BYTES:
                raise ValueError(f"Image {filename} exceeds 10MB.")
            encoded = base64.b64encode(content).decode("ascii")
            payloads.append(
                {
                    "name": filename,
                    "content_type": content_type,
                    "data_url": f"data:{content_type};base64,{encoded}",
                }
            )
        return payloads

    def _get_text_client(self) -> OpenAI:
        if self._text_client is None:
            http_client = httpx.Client(
                timeout=httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=30.0),
                verify=settings.SSL_VERIFY,
            )
            self._text_client = OpenAI(
                api_key=settings.get_text_api_key(),
                base_url=settings.get_text_base_url(),
                http_client=http_client,
                timeout=120.0,
            )
        return self._text_client

    def _get_vision_client(self) -> OpenAI:
        if self._vision_client is None:
            http_client = httpx.Client(
                timeout=httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=30.0),
                verify=settings.SSL_VERIFY,
            )
            self._vision_client = OpenAI(
                api_key=settings.VISION_API_KEY,
                base_url=settings.VISION_BASE_URL,
                http_client=http_client,
                timeout=120.0,
            )
        return self._vision_client

    @staticmethod
    def _build_suggested_actions(mode: str, run: Optional[dict[str, Any]]) -> list[str]:
        actions: list[str] = []
        if mode == "testplan":
            actions.extend(["先核对缺失参数和引脚方向。", "对 warning 较多的页面优先人工复核。"])
        elif mode == "resource-map":
            actions.extend(["确认电源 rail 定义是否完整。", "核对双工位和 PGS 配置是否一致。"])
        elif mode == "codegen":
            actions.extend(["优先检查平台 API 调用和量程设置。", "对 compile / static warning 逐项复核。"])
        elif mode == "diagnosis":
            actions.extend(["先看异常比例和最近波形趋势。", "结合已知故障主题逐步缩小根因范围。"])
        elif mode == "run-analysis":
            actions.extend(["优先查看当前 step 的 warnings / errors。", "确认是否需要批准、打回或补充输入。"])

        if run and run.get("status") == "human_review_required":
            actions.append("当前 run 在等待人工复核，建议先查看 review summary 再决定批准或打回。")
        return actions[:4]


_chat_service: Optional[EngineerAssistantChatService] = None


def get_engineer_assistant_chat_service() -> EngineerAssistantChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = EngineerAssistantChatService()
    return _chat_service

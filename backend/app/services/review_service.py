"""LLM-assisted review aggregation with deterministic normalization."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from openai import OpenAI

from app.core.config import get_settings

settings = get_settings()

REVIEW_SYSTEM_PROMPT = """你是 ATE 测试工程复核专家。
你需要根据全链路 ATE 开发过程中的中间产物和校验结果，输出结构化复核结论。

请严格输出 JSON，不要输出其他内容：
{
  "risk_level": "low" | "medium" | "high",
  "summary": "总体评估概述",
  "must_review_items": ["必须人工复核的阻断项"],
  "recommendations": ["建议人工确认或后续优化的项"],
  "confidence_score": 0.0-1.0
}

规则：
1. 自动生成结果永远不能视为可直接上机。
2. 参数校验失败、静态检查失败、真实编译预检失败都应提升为高风险。
3. RAG 未命中、降级策略、普通 warning 更适合作为 recommendations，而不是 must_review_items。
4. VECDIO/PGS 依赖存在时，应要求人工复核对应配置。
5. confidence_score 与整体步骤质量相关。
"""


class ReviewService:
    """Aggregate run evidence and produce a normalized review summary."""

    def __init__(self) -> None:
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> Optional[OpenAI]:
        if self._client is None and settings.DEEPSEEK_API_KEY:
            self._client = OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
            )
        return self._client

    def generate_review(
        self,
        shared: Dict[str, Any],
        *,
        steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        review_input = self._build_review_input(shared, steps=steps)

        if not self.client:
            return self._fallback_review(review_input)

        try:
            response = self.client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(review_input, ensure_ascii=False, indent=2)},
                ],
                temperature=0.1,
                max_tokens=1024,
            )
            content = response.choices[0].message.content or ""
            parsed = self._parse_response(content)
            return self._normalize_review(parsed, review_input)
        except Exception:
            return self._fallback_review(review_input)

    def _build_review_input(
        self,
        shared: Dict[str, Any],
        *,
        steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        validation = shared.get("validation") or {}
        rag = shared.get("rag") or {}
        generated_result = shared.get("generated_result") or {}
        plan = generated_result.get("plan") or shared.get("plan") or {}
        static_analysis = generated_result.get("static_analysis") or {}
        compile_validation = generated_result.get("compile_validation") or {}
        package_export = generated_result.get("package_export") or {}
        resource_map_result = shared.get("resource_map_result") or {}

        quality_summary = self._aggregate_step_quality(steps or [])

        return {
            "parameter_validation": {
                "passed": validation.get("passed"),
                "missing_field_count": len(validation.get("missing_fields") or []),
                "warning_count": len(validation.get("warnings") or []),
            },
            "rag_retrieval": {
                "hit_count": rag.get("hit_count", 0),
                "fallback_used": rag.get("fallback_used", False) or not rag.get("ready", True),
            },
            "codegen_plan": {
                "selected_items": plan.get("selected_items"),
                "requires_vector": plan.get("requires_vector", False),
                "requires_pgs": plan.get("requires_pgs", False),
                "errors": plan.get("errors"),
            },
            "generated_code": {
                "filename": generated_result.get("filename"),
                "function_count": self._count_generated_functions(generated_result.get("functions")),
            },
            "resource_mapping": {
                "warning_count": len(resource_map_result.get("warnings") or []),
                "error_count": len(resource_map_result.get("errors") or []),
            },
            "static_analysis": {
                "passed": static_analysis.get("passed"),
                "issue_count": len(static_analysis.get("issues") or []),
            },
            "compile_validation": {
                "attempted": compile_validation.get("attempted"),
                "passed": compile_validation.get("passed"),
                "issue_count": len(compile_validation.get("issues") or compile_validation.get("diagnostics") or []),
                "mode": compile_validation.get("mode", "unknown"),
                "compiler": compile_validation.get("compiler"),
            },
            "engineering_package": {
                "exported": bool(package_export),
            },
            "step_quality": quality_summary,
        }

    @staticmethod
    def _count_generated_functions(functions: Any) -> int:
        if isinstance(functions, int):
            return functions
        if isinstance(functions, list):
            return len(functions)
        return 0

    @staticmethod
    def _aggregate_step_quality(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        scores: List[float] = []
        fallback_steps: List[str] = []
        risk_flags: List[str] = []

        for step in steps:
            quality = step.get("quality")
            if not quality:
                continue
            agent = step.get("agent", "unknown")
            scores.append(float(quality.get("score", 1.0)))
            if quality.get("fallback_used"):
                fallback_steps.append(agent)
            for flag in quality.get("risk_flags") or []:
                risk_flags.append(f"[{agent}] {flag}")

        avg_score = round(sum(scores) / len(scores), 2) if scores else 1.0
        min_score = min(scores) if scores else 1.0
        return {
            "average": avg_score,
            "minimum": min_score,
            "step_count": len(scores),
            "fallback_steps": fallback_steps,
            "global_risk_flags": risk_flags[:10],
        }

    def _parse_response(self, content: str) -> Dict[str, Any]:
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return self._default_review()

    def _normalize_review(self, review: Dict[str, Any], review_input: Dict[str, Any]) -> Dict[str, Any]:
        validation = review_input.get("parameter_validation", {})
        rag = review_input.get("rag_retrieval", {})
        plan = review_input.get("codegen_plan", {})
        static = review_input.get("static_analysis", {})
        compile_val = review_input.get("compile_validation", {})
        resource_mapping = review_input.get("resource_mapping", {})
        quality = review_input.get("step_quality", {})

        must_review_items: List[str] = [
            "生成结果仅用于辅助 ATE 测试开发，需由 ATE 工程师复核后再上机使用。",
        ]
        recommendations: List[str] = list(review.get("recommendations") or [])
        risk_level = str(review.get("risk_level") or "medium").lower()

        if not validation.get("passed", False):
            must_review_items.append("参数校验未完全通过，请先确认提取结果是否足以支撑后续工程。")
            risk_level = "high"
        elif validation.get("warning_count", 0):
            recommendations.append(f"参数校验中有 {validation['warning_count']} 个警告，建议人工确认关键参数和电源定义。")

        if static.get("passed") is False:
            must_review_items.append("静态检查存在未修复问题，请先修复后再继续。")
            risk_level = "high"

        compile_attempted = compile_val.get("attempted")
        compile_passed = compile_val.get("passed")
        compile_issue_count = compile_val.get("issue_count", 0)
        if compile_attempted is False:
            recommendations.append("当前环境未执行真实编译预检，请在具备 STS 工具链的环境中补做编译验证。")
        elif compile_passed is False:
            must_review_items.append(f"编译预检未通过，请查看 {compile_issue_count or '相关'} 条诊断并修复后再继续。")
            risk_level = "high"

        if resource_mapping.get("error_count", 0):
            must_review_items.append("资源映射存在错误，请先确认引脚分配和适配器资源配置。")
            risk_level = "high"
        elif resource_mapping.get("warning_count", 0):
            recommendations.append(f"资源映射中有 {resource_mapping['warning_count']} 个警告，建议复核站点配置和方向切换。")

        if rag.get("hit_count", 0) == 0:
            recommendations.append("RAG 检索未命中，将更多依赖模板与企业知识；请人工确认平台 API 和流程适配性。")
        elif rag.get("fallback_used"):
            recommendations.append("RAG 使用了降级策略，建议额外确认平台 API 和关键流程调用。")

        if plan.get("requires_vector") or plan.get("requires_pgs"):
            must_review_items.append("当前结果依赖 VECDIO/PGS 配置，请复核 vector、label、time set、PGS 与 AutoLoad。")

        if quality.get("minimum", 1.0) < 0.5:
            risk_level = "high"
            recommendations.append(f"存在低质量步骤（最低分 {quality['minimum']}），建议结合时间线重点排查。")

        fallback_steps = quality.get("fallback_steps") or []
        if fallback_steps:
            recommendations.append(f"以下步骤使用了降级策略，建议重点复核：{', '.join(fallback_steps)}")

        if risk_level not in {"low", "medium", "high"}:
            risk_level = "medium"

        return {
            "overall_status": "needs_human_review",
            "risk_level": risk_level,
            "summary": review.get("summary") or "全链路结果已生成，但仍需工程师结合校验结果和中间产物完成复核。",
            "must_review_items": list(dict.fromkeys(must_review_items)),
            "recommendations": list(dict.fromkeys(recommendations))
            or ["建议结合运行中心与工程包，逐项完成测试工程复核。"],
            "confidence_score": float(review.get("confidence_score", quality.get("average", 0.0)) or 0.0),
        }

    def _fallback_review(self, review_input: Dict[str, Any]) -> Dict[str, Any]:
        return self._normalize_review(self._default_review(), review_input)

    @staticmethod
    def _default_review() -> Dict[str, Any]:
        return {
            "overall_status": "needs_human_review",
            "summary": "全链路结果已生成，但仍需工程师结合校验结果和中间产物完成复核。",
            "risk_level": "medium",
            "must_review_items": [],
            "recommendations": [],
            "confidence_score": 0.0,
        }

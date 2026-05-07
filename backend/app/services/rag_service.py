"""
RAG service for STS8200S handbook retrieval and code-generation augmentation.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx
from openai import OpenAI

from app.core.config import get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger = setup_logger()

try:
    import chromadb

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("chromadb not installed, RAG will use TF-IDF fallback mode.")

try:
    import pdfplumber

    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logger.warning("pdfplumber not installed, PDF handbook parsing is unavailable.")


COLLECTION_NAME = "sts8200s_manual"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
TOP_K_DEFAULT = 5
EMBED_BATCH_SIZE = 32

DEFAULT_RETRIEVAL_HINTS = [
    "STS8200S",
    "ATE",
    "StsGetParam",
    "SetTestResult",
]

SCENARIO_RETRIEVAL_HINTS = {
    "digital": ["DIO", "RunVector", "SetPinLevel", "VIH", "VIL", "VOH", "VOL"],
    "analog": ["FOVI", "PMU", "MeasureVI", "LDO", "IQ", "UVLO", "ENT"],
    "multisite": ["PGS", "Site", "AutoLoad", "resource mapping"],
    "custom": ["FOVI", "PMU", "DIO"],
}

TEST_ITEM_RETRIEVAL_HINTS = {
    "CON": ["continuity", "open short", "FOVI"],
    "FUN": ["RunVector", "DIO", "functional test", "SetPinLevel"],
    "VIH": ["VIH", "DIO", "SetPinLevel"],
    "VIL": ["VIL", "DIO", "SetPinLevel"],
    "VIK": ["VIK", "PMU", "FOVI"],
    "VOH": ["VOH", "PMU", "FOVI"],
    "VOL": ["VOL", "PMU", "FOVI"],
    "IOS": ["IOS", "PMU", "FOVI"],
    "II": ["II", "QTMU", "leakage"],
    "IIN": ["IIH", "IIL", "QTMU", "leakage"],
    "ICC": ["ICC", "MeasureVI", "FOVI"],
    "TP1": ["timing", "ACSM", "tPHL"],
    "TP2": ["timing", "ACSM", "tPHL"],
    "TP3": ["timing", "ACSM", "tPLH"],
    "TP4": ["timing", "ACSM", "tPLH"],
    "VO": ["VO", "FOVI", "MeasureVI"],
    "LNR": ["line regulation", "FOVI", "PMU"],
    "LDR": ["load regulation", "FOVI", "PMU"],
    "VDO1": ["dropout", "LDO", "FOVI"],
    "VDO2": ["dropout", "LDO", "FOVI"],
    "ICL": ["current limit", "FOVI", "PMU"],
    "TP": ["timing", "startup", "ACSM"],
    "UVLO": ["UVLO", "threshold", "FOVI"],
    "ENT": ["enable threshold", "ENT", "FOVI"],
    "IGND": ["ground current", "IQ", "MeasureVI"],
    "IQ": ["quiescent current", "IQ", "MeasureVI"],
}


class RAGService:
    """RAG retrieval and prompt-injection service for the STS8200S handbook."""

    def __init__(self) -> None:
        self._client: Optional[OpenAI] = None
        self._chroma: Optional[object] = None
        self._collection = None
        self._tfidf_docs: List[Dict] = []
        self._ready = False
        self._doc_count = 0
        self._index_hash = ""
        self._init_vector_store()

    @property
    def is_ready(self) -> bool:
        return self._ready and self._doc_count > 0

    @property
    def status(self) -> Dict:
        return {
            "ready": self.is_ready,
            "doc_count": self._doc_count,
            "backend": "chromadb" if CHROMADB_AVAILABLE else "tfidf",
            "index_hash": self._index_hash,
        }

    def build_index(self, pdf_path: str) -> Dict:
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"Handbook file does not exist: {pdf_path}")

        logger.info(f"Building RAG index from PDF: {path.name}")
        chunks = self._extract_pdf_chunks(str(path))
        if not chunks:
            raise ValueError("No usable handbook text was extracted from the PDF.")

        file_hash = hashlib.md5(path.read_bytes()).hexdigest()[:8]
        if CHROMADB_AVAILABLE:
            self._build_chromadb_index(chunks, file_hash)
        else:
            self._build_tfidf_index(chunks)

        self._index_hash = file_hash
        self._ready = True
        self._doc_count = len(chunks)
        logger.info(f"RAG index ready with {len(chunks)} chunks.")
        return {"chunks": len(chunks), "hash": file_hash}

    def build_index_from_text(self, sections: List[Dict[str, str]]) -> Dict:
        chunks: List[Dict] = []
        for index, section in enumerate(sections):
            chunks.append(
                {
                    "id": f"manual_{index:04d}",
                    "text": f"[{section.get('title', '')}]\n{section['content']}",
                    "source": section.get("title", f"section_{index}"),
                    "page": section.get("page", 0),
                }
            )

        if CHROMADB_AVAILABLE:
            self._build_chromadb_index(chunks, "manual_text")
        else:
            self._build_tfidf_index(chunks)

        self._ready = True
        self._doc_count = len(chunks)
        self._index_hash = "manual_text"
        logger.info(f"Built text RAG index with {len(chunks)} chunks.")
        return {"chunks": len(chunks), "hash": "manual_text"}

    def retrieve(
        self,
        query: str,
        top_k: int = TOP_K_DEFAULT,
        *,
        chip_name: Optional[str] = None,
        chip_type: Optional[str] = None,
        test_items: Optional[List[str]] = None,
        api_hints: Optional[List[str]] = None,
    ) -> List[Dict]:
        if not self.is_ready:
            return []

        queries = self.build_query_variants(
            query,
            chip_name=chip_name,
            chip_type=chip_type,
            test_items=test_items,
            api_hints=api_hints,
        )
        aggregated: Dict[Tuple[str, str], Dict] = {}
        for index, candidate in enumerate(queries):
            if CHROMADB_AVAILABLE and self._collection is not None:
                current = self._chromadb_retrieve(candidate, top_k)
            else:
                current = self._tfidf_retrieve(candidate, top_k)

            for item in current:
                key = (item.get("source", ""), item.get("text", ""))
                candidate_score = float(item.get("score", 0.0)) + max(0.0, 0.12 - index * 0.02)
                enriched = dict(item)
                enriched["score"] = round(candidate_score, 3)
                enriched.setdefault("matched_query", candidate)
                existing = aggregated.get(key)
                if existing is None or candidate_score > float(existing.get("score", 0.0)):
                    aggregated[key] = enriched

        ranked = sorted(
            aggregated.values(),
            key=lambda item: float(item.get("score", 0.0)),
            reverse=True,
        )
        return ranked[:top_k]

    def build_query_variants(
        self,
        query: str,
        *,
        chip_name: Optional[str] = None,
        chip_type: Optional[str] = None,
        test_items: Optional[List[str]] = None,
        api_hints: Optional[List[str]] = None,
    ) -> List[str]:
        base = str(query or "").strip()
        scenario = self._resolve_scenario(chip_type)
        items = [str(item).strip().upper() for item in (test_items or []) if str(item).strip()]
        hints: List[str] = []
        seen: set[str] = set()

        def push(values: List[str]) -> None:
            for value in values:
                normalized = str(value or "").strip()
                if not normalized:
                    continue
                key = normalized.lower()
                if key not in seen:
                    seen.add(key)
                    hints.append(normalized)

        push(DEFAULT_RETRIEVAL_HINTS)
        push(SCENARIO_RETRIEVAL_HINTS.get(scenario, []))
        for item in items:
            push([item])
            push(TEST_ITEM_RETRIEVAL_HINTS.get(item, []))
        push([str(chip_name or "").strip(), str(chip_type or "").strip()])
        push(list(api_hints or []))
        push(self._extract_api_like_tokens(base))

        variants: List[str] = []
        if base:
            variants.append(base)
        if base or hints:
            variants.append(" ".join(part for part in [base, *hints[:8]] if part).strip())
        if chip_name or chip_type or items:
            variants.append(
                " ".join(
                    part
                    for part in [
                        "STS8200S",
                        str(chip_name or "").strip(),
                        str(chip_type or "").strip(),
                        " ".join(items[:6]),
                        " ".join(hints[:10]),
                    ]
                    if part
                ).strip()
            )
        variants.append(" ".join(hints[:12]).strip())

        deduped: List[str] = []
        used: set[str] = set()
        for variant in variants:
            normalized = " ".join(variant.split())
            if normalized and normalized.lower() not in used:
                used.add(normalized.lower())
                deduped.append(normalized)

        return deduped or ["STS8200S StsGetParam SetTestResult FOVI DIO PMU"]

    def generate_with_rag(
        self,
        user_query: str,
        chip_name: str,
        chip_type: str,
        skeleton_code: str = "",
        extra_context: str = "",
        test_items: Optional[List[str]] = None,
        api_hints: Optional[List[str]] = None,
    ) -> Tuple[str, List[Dict]]:
        retrieved = self.retrieve(
            user_query,
            top_k=TOP_K_DEFAULT,
            chip_name=chip_name,
            chip_type=chip_type,
            test_items=test_items,
            api_hints=api_hints,
        )
        context_text = self._format_context(retrieved)
        prompt = self._build_rag_prompt(
            user_query=user_query,
            chip_name=chip_name,
            chip_type=chip_type,
            context_text=context_text,
            skeleton_code=skeleton_code,
            extra_context=extra_context,
        )

        client = self._get_llm_client()
        resp = client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=settings.MAX_TOKENS,
        )
        raw = (resp.choices[0].message.content or "").strip()
        return self._extract_code_block(raw), retrieved

    def _extract_pdf_chunks(self, pdf_path: str) -> List[Dict]:
        if not PDFPLUMBER_AVAILABLE:
            return []

        chunks: List[Dict] = []
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            page_map = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                page_map.append((len(full_text), page.page_number))
                full_text += text + "\n"

        start = 0
        index = 0
        while start < len(full_text):
            end = min(start + CHUNK_SIZE, len(full_text))
            text = full_text[start:end].strip()
            if len(text) > 50:
                page_no = 1
                for offset, page_number in page_map:
                    if offset <= start:
                        page_no = page_number
                chunks.append(
                    {
                        "id": f"chunk_{index:04d}",
                        "text": text,
                        "source": f"STS8200S manual P{page_no}",
                        "page": page_no,
                    }
                )
                index += 1
            start += CHUNK_SIZE - CHUNK_OVERLAP

        return chunks

    def _init_vector_store(self) -> None:
        if not CHROMADB_AVAILABLE:
            return
        try:
            persist_dir = str(settings.PROCESSED_DIR / "rag_index")
            Path(persist_dir).mkdir(parents=True, exist_ok=True)
            self._chroma = chromadb.PersistentClient(path=persist_dir)
            try:
                self._collection = self._chroma.get_collection(COLLECTION_NAME)
                count = self._collection.count()
                if count > 0:
                    self._doc_count = count
                    self._ready = True
                    logger.info(f"Loaded existing RAG index with {count} chunks.")
            except Exception:
                pass
        except Exception as exc:
            logger.warning(f"ChromaDB initialization failed: {exc}")

    def _build_chromadb_index(self, chunks: List[Dict], file_hash: str) -> None:
        try:
            try:
                self._chroma.delete_collection(COLLECTION_NAME)
            except Exception:
                pass

            self._collection = self._chroma.create_collection(
                COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )

            client = self._get_llm_client()
            texts = [chunk["text"] for chunk in chunks]
            embeds = []
            for index in range(0, len(texts), EMBED_BATCH_SIZE):
                batch = texts[index : index + EMBED_BATCH_SIZE]
                resp = client.embeddings.create(
                    model="deepseek-embed" if "deepseek" in settings.DEEPSEEK_BASE_URL else "text-embedding-ada-002",
                    input=batch,
                )
                embeds.extend(item.embedding for item in resp.data)

            self._collection.add(
                ids=[chunk["id"] for chunk in chunks],
                embeddings=embeds,
                documents=[chunk["text"] for chunk in chunks],
                metadatas=[{"source": chunk["source"], "page": chunk["page"], "hash": file_hash} for chunk in chunks],
            )
        except Exception as exc:
            logger.warning(f"ChromaDB indexing failed, falling back to TF-IDF: {exc}")
            self._build_tfidf_index(chunks)

    def _chromadb_retrieve(self, query: str, top_k: int) -> List[Dict]:
        client = self._get_llm_client()
        try:
            resp = client.embeddings.create(
                model="deepseek-embed" if "deepseek" in settings.DEEPSEEK_BASE_URL else "text-embedding-ada-002",
                input=[query],
            )
            q_embed = resp.data[0].embedding
            results = self._collection.query(query_embeddings=[q_embed], n_results=top_k)
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            dists = results["distances"][0]
            return [
                {"text": doc, "source": meta["source"], "score": round(1 - dist, 3)}
                for doc, meta, dist in zip(docs, metas, dists)
            ]
        except Exception as exc:
            logger.warning(f"ChromaDB retrieval failed, falling back to TF-IDF: {exc}")
            return self._tfidf_retrieve(query, top_k)

    def _build_tfidf_index(self, chunks: List[Dict]) -> None:
        self._tfidf_docs = chunks
        logger.info(f"TF-IDF index ready with {len(chunks)} chunks.")

    def _tfidf_retrieve(self, query: str, top_k: int) -> List[Dict]:
        if not self._tfidf_docs:
            return []

        q_tokens = set(re.findall(r"\w+", query.lower()))
        if not q_tokens:
            return []

        scored = []
        for doc in self._tfidf_docs:
            d_tokens = set(re.findall(r"\w+", doc["text"].lower()))
            overlap = len(q_tokens & d_tokens)
            if overlap > 0:
                scored.append((overlap, doc))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {"text": doc["text"], "source": doc["source"], "score": round(score / max(len(q_tokens), 1), 3)}
            for score, doc in scored[:top_k]
        ]

    @staticmethod
    def _extract_api_like_tokens(text: str) -> List[str]:
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9_]{2,}", str(text or ""))
        return [
            token
            for token in tokens
            if token.upper() == token or any(ch.isupper() for ch in token[1:])
        ][:10]

    @staticmethod
    def _resolve_scenario(chip_type: Optional[str]) -> str:
        value = str(chip_type or "").strip().upper()
        if value in {"DIGITAL", "DIGITAL_74", "DIGITAL_54", "DIGITAL_4000", "MEMORY"}:
            return "digital"
        if value in {"LDO", "ANALOG_GENERAL", "ANALOG", "LDO_ANALOG"}:
            return "analog"
        if value in {"MULTISITE"}:
            return "multisite"
        raw = str(chip_type or "").strip().lower()
        if raw == "digital":
            return "digital"
        if raw == "ldo":
            return "analog"
        return "custom"

    def _build_rag_prompt(
        self,
        user_query: str,
        chip_name: str,
        chip_type: str,
        context_text: str,
        skeleton_code: str,
        extra_context: str,
    ) -> str:
        skeleton_section = (
            f"\n[Base scaffold code]\n```cpp\n{skeleton_code}\n```\n" if skeleton_code else ""
        )
        return f"""You are a senior STS8200S ATE engineer.
Generate STS8200S-style C++ test code for chip {chip_name} ({chip_type}) using the handbook context below.

[Engineer request]
{user_query}

[STS8200S handbook context]
{context_text}

{extra_context}
{skeleton_section}
[Requirements]
1. Include DUT_API void HardWareCfg() and DUT_API void InitBeforeTestFlow().
2. Each test function must call StsGetParam() and SetTestResult().
3. Prefer handbook-accurate FOVI/PMU/DIO API names and ranges.
4. Add concise professional comments for bench engineers.
5. Return only complete C++ code wrapped in ```cpp```."""

    @staticmethod
    def _format_context(chunks: List[Dict]) -> str:
        if not chunks:
            return "(No handbook chunk matched. Fall back to enterprise knowledge and scaffold.)"
        parts = []
        for index, chunk in enumerate(chunks, start=1):
            score_str = f"score={chunk['score']:.2f}" if "score" in chunk else ""
            parts.append(f"[Chunk {index} | {chunk.get('source', '')} {score_str}]\n{chunk['text']}")
        return "\n\n".join(parts)

    @staticmethod
    def _extract_code_block(raw: str) -> str:
        match = re.search(r"```(?:cpp|c\+\+)?\s*([\s\S]+?)```", raw, re.IGNORECASE)
        return match.group(1).strip() if match else raw

    def _get_llm_client(self) -> OpenAI:
        if self._client is None:
            http_client = httpx.Client(
                timeout=httpx.Timeout(connect=30, read=120, write=30, pool=30),
                verify=settings.SSL_VERIFY,
            )
            self._client = OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
                http_client=http_client,
                timeout=120.0,
            )
        return self._client


_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service


STS8200S_BUILTIN_KNOWLEDGE = [
    {
        "title": "FOVI force-voltage measurement",
        "content": """UserFOVI or FOVI channels are used to force voltage and measure current.
Typical ranges include FOVI_1V, FOVI_2V, FOVI_5V, FOVI_10V, FOVI_20V and FOVI_50V.
Use GetFOVI_Meas or PMU-style readback APIs after forcing voltage.""",
    },
    {
        "title": "QTMU precision current measurement",
        "content": """QTMU is suited for small current and leakage measurement.
Typical scenarios include IQ, leakage, and threshold sweeps with uA or nA-level precision.""",
    },
    {
        "title": "DIO vector execution",
        "content": """Digital tests rely on DIO setup, SetPinLevel, Connect, Disconnect, and Run or RunVector APIs.
FUN, VIH, and VIL often combine vector labels with pin-level thresholds.""",
    },
    {
        "title": "Parameter APIs",
        "content": """Each DUT_API int test function should call StsGetParam(funcindex, "PARAM_NAME").
Use SetTestResult and SetResultRemark to report values and labels back to the platform.""",
    },
    {
        "title": "Hardware lifecycle hooks",
        "content": """Generated programs should keep HardWareCfg, InitBeforeTestFlow, InitAfterTestFlow, and SetupFailSite stable.
HardWareCfg usually calls STSSetHardwareCheck(FALSE) in generated development scaffolds.""",
    },
    {
        "title": "LDO dropout and regulation",
        "content": """LDO flows often use FOVI or PMU resources to sweep VIN, load VOUT, and measure dropout.
Typical tests include VDO1, VDO2, line regulation, load regulation, IQ, and UVLO.""",
    },
    {
        "title": "Continuity and open-short",
        "content": """CON or continuity tests typically force a small voltage or current with PMU/FOVI and inspect the response.
Pin-level continuity is often reported per channel with remarks for pin names.""",
    },
    {
        "title": "Timing and ACSM",
        "content": """Timing items such as TP1, TP2, TP3, and TP4 may rely on ACSM-style measurement and vector timing context.
Use clear labels for tPHL, tPLH, rise time, and fall time when the timing path is known.""",
    },
]

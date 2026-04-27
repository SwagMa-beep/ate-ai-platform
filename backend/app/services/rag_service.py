"""
RAG 服务 - 基于 STS8200S 编程手册的检索增强代码生成
架构：PDF 切片 → DeepSeek Embedding → ChromaDB 向量库 → 语义检索 → Prompt 注入
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import httpx
from openai import OpenAI

from app.core.config import get_settings
from app.utils.logger import setup_logger

settings = get_settings()
logger   = setup_logger()

# ── ChromaDB 懒加载（可选依赖）─────────────────────────────────────
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("chromadb 未安装，RAG 功能将使用 TF-IDF 降级模式")

# ── pdfplumber 用于读取手册 PDF ───────────────────────────────────
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False


COLLECTION_NAME  = "sts8200s_manual"
CHUNK_SIZE       = 800    # 字符数，约半页
CHUNK_OVERLAP    = 100
TOP_K_DEFAULT    = 5
EMBED_BATCH_SIZE = 32     # DeepSeek embedding 每次最多条数


class RAGService:
    """STS8200S 编程手册 RAG 检索服务"""

    def __init__(self):
        self._client: Optional[OpenAI] = None
        self._chroma: Optional[object] = None
        self._collection = None
        self._tfidf_docs: List[Dict] = []   # 降级模式存储
        self._ready = False
        self._doc_count = 0
        self._index_hash = ""

        # 尝试加载已有索引
        self._init_vector_store()

    # ── 公共属性 ──────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        return self._ready and self._doc_count > 0

    @property
    def status(self) -> Dict:
        return {
            "ready":       self.is_ready,
            "doc_count":   self._doc_count,
            "backend":     "chromadb" if CHROMADB_AVAILABLE else "tfidf",
            "index_hash":  self._index_hash,
        }

    # ── 索引构建 ──────────────────────────────────────────────────

    def build_index(self, pdf_path: str) -> Dict:
        """读取 STS8200S 编程手册 PDF，构建向量索引。"""
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"手册文件不存在: {pdf_path}")

        logger.info(f"开始构建 RAG 索引: {path.name}")

        # 读取 PDF 文本
        chunks = self._extract_pdf_chunks(str(path))
        if not chunks:
            raise ValueError("PDF 解析失败或内容为空")

        logger.info(f"  切片数量: {len(chunks)}")

        # 计算文件哈希（避免重复建索引）
        file_hash = hashlib.md5(path.read_bytes()).hexdigest()[:8]

        if CHROMADB_AVAILABLE:
            self._build_chromadb_index(chunks, file_hash)
        else:
            self._build_tfidf_index(chunks)

        self._index_hash = file_hash
        self._ready = True
        self._doc_count = len(chunks)

        logger.info(f"✅ RAG 索引构建完成: {len(chunks)} 个片段")
        return {"chunks": len(chunks), "hash": file_hash}

    def build_index_from_text(self, sections: List[Dict[str, str]]) -> Dict:
        """
        从结构化文本片段直接建索引（用于手动注入编程手册内容）。
        sections: [{"title": str, "content": str}, ...]
        """
        chunks = []
        for i, sec in enumerate(sections):
            chunks.append({
                "id":      f"manual_{i:04d}",
                "text":    f"【{sec.get('title', '')}】\n{sec['content']}",
                "source":  sec.get("title", f"section_{i}"),
                "page":    sec.get("page", 0),
            })

        if CHROMADB_AVAILABLE:
            self._build_chromadb_index(chunks, "manual_text")
        else:
            self._build_tfidf_index(chunks)

        self._ready = True
        self._doc_count = len(chunks)
        self._index_hash = "manual_text"
        logger.info(f"✅ 文本 RAG 索引构建完成: {len(chunks)} 片段")
        return {"chunks": len(chunks), "hash": "manual_text"}

    # ── 检索 ──────────────────────────────────────────────────────

    def retrieve(self, query: str, top_k: int = TOP_K_DEFAULT) -> List[Dict]:
        """语义检索，返回最相关的手册片段。"""
        if not self.is_ready:
            return []

        if CHROMADB_AVAILABLE and self._collection is not None:
            return self._chromadb_retrieve(query, top_k)
        else:
            return self._tfidf_retrieve(query, top_k)

    # ── RAG 代码生成 ──────────────────────────────────────────────

    def generate_with_rag(
        self,
        user_query: str,
        chip_name:  str,
        chip_type:  str,
        skeleton_code: str = "",
        extra_context: str = "",
    ) -> Tuple[str, List[Dict]]:
        """
        检索手册片段 → 注入 Prompt → DeepSeek 生成代码。

        Returns:
            (generated_code: str, retrieved_chunks: List[Dict])
        """
        # 1. 检索相关片段
        retrieved = self.retrieve(user_query, top_k=TOP_K_DEFAULT)
        context_text = self._format_context(retrieved)

        # 2. 构建 RAG Prompt
        prompt = self._build_rag_prompt(
            user_query    = user_query,
            chip_name     = chip_name,
            chip_type     = chip_type,
            context_text  = context_text,
            skeleton_code = skeleton_code,
            extra_context = extra_context,
        )

        # 3. 调用 DeepSeek
        client = self._get_llm_client()
        resp = client.chat.completions.create(
            model       = settings.DEEPSEEK_MODEL,
            messages    = [{"role": "user", "content": prompt}],
            temperature = 0.2,
            max_tokens  = settings.MAX_TOKENS,
        )
        raw = resp.choices[0].message.content.strip()

        # 4. 提取代码块
        code = self._extract_code_block(raw)
        return code, retrieved

    # ── 私有：PDF 解析 ────────────────────────────────────────────

    def _extract_pdf_chunks(self, pdf_path: str) -> List[Dict]:
        chunks = []
        if not PDFPLUMBER_AVAILABLE:
            logger.warning("pdfplumber 未安装，无法解析 PDF")
            return chunks

        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            page_map  = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                page_map.append((len(full_text), page.page_number))
                full_text += text + "\n"

        # 滑动窗口切片
        start = 0
        idx   = 0
        while start < len(full_text):
            end  = min(start + CHUNK_SIZE, len(full_text))
            text = full_text[start:end].strip()
            if len(text) > 50:
                # 找所在页
                page_no = 1
                for offset, pno in page_map:
                    if offset <= start:
                        page_no = pno
                chunks.append({
                    "id":     f"chunk_{idx:04d}",
                    "text":   text,
                    "source": f"STS8200S编程手册 P{page_no}",
                    "page":   page_no,
                })
                idx += 1
            start += CHUNK_SIZE - CHUNK_OVERLAP

        return chunks

    # ── 私有：ChromaDB 索引 ───────────────────────────────────────

    def _init_vector_store(self):
        if not CHROMADB_AVAILABLE:
            return
        try:
            persist_dir = str(settings.PROCESSED_DIR / "rag_index")
            Path(persist_dir).mkdir(parents=True, exist_ok=True)
            self._chroma = chromadb.PersistentClient(path=persist_dir)
            # 尝试加载已有 collection
            try:
                self._collection = self._chroma.get_collection(COLLECTION_NAME)
                count = self._collection.count()
                if count > 0:
                    self._doc_count = count
                    self._ready = True
                    logger.info(f"加载已有 RAG 索引: {count} 条")
            except Exception:
                pass  # collection 不存在
        except Exception as e:
            logger.warning(f"ChromaDB 初始化失败: {e}")

    def _build_chromadb_index(self, chunks: List[Dict], file_hash: str):
        """使用 DeepSeek embedding 构建 ChromaDB 索引。"""
        try:
            # 删除旧 collection（重建）
            try:
                self._chroma.delete_collection(COLLECTION_NAME)
            except Exception:
                pass

            self._collection = self._chroma.create_collection(
                COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )

            # 批量 embedding
            client = self._get_llm_client()
            texts  = [c["text"] for c in chunks]
            embeds = []

            for i in range(0, len(texts), EMBED_BATCH_SIZE):
                batch = texts[i: i + EMBED_BATCH_SIZE]
                resp  = client.embeddings.create(
                    model = "deepseek-embed" if "deepseek" in settings.DEEPSEEK_BASE_URL else "text-embedding-ada-002",
                    input = batch,
                )
                embeds.extend([d.embedding for d in resp.data])
                logger.debug(f"  Embedding 进度: {min(i+EMBED_BATCH_SIZE, len(texts))}/{len(texts)}")

            self._collection.add(
                ids        = [c["id"]     for c in chunks],
                embeddings = embeds,
                documents  = [c["text"]   for c in chunks],
                metadatas  = [{"source": c["source"], "page": c["page"]} for c in chunks],
            )
        except Exception as e:
            logger.warning(f"ChromaDB embedding 失败，降级到 TF-IDF: {e}")
            self._build_tfidf_index(chunks)

    def _chromadb_retrieve(self, query: str, top_k: int) -> List[Dict]:
        client = self._get_llm_client()
        try:
            resp   = client.embeddings.create(
                model = "deepseek-embed" if "deepseek" in settings.DEEPSEEK_BASE_URL else "text-embedding-ada-002",
                input = [query],
            )
            q_embed = resp.data[0].embedding
            results = self._collection.query(
                query_embeddings = [q_embed],
                n_results        = top_k,
            )
            docs  = results["documents"][0]
            metas = results["metadatas"][0]
            dists = results["distances"][0]
            return [
                {"text": d, "source": m["source"], "score": round(1 - dist, 3)}
                for d, m, dist in zip(docs, metas, dists)
            ]
        except Exception as e:
            logger.warning(f"ChromaDB 检索失败，降级到 TF-IDF: {e}")
            return self._tfidf_retrieve(query, top_k)

    # ── 私有：TF-IDF 降级 ─────────────────────────────────────────

    def _build_tfidf_index(self, chunks: List[Dict]):
        self._tfidf_docs = chunks
        logger.info(f"  TF-IDF 索引: {len(chunks)} 片段")

    def _tfidf_retrieve(self, query: str, top_k: int) -> List[Dict]:
        """基于关键词重叠的简单检索（无需向量）"""
        if not self._tfidf_docs:
            return []

        q_tokens = set(re.findall(r'\w+', query.lower()))
        scored = []
        for doc in self._tfidf_docs:
            d_tokens = set(re.findall(r'\w+', doc["text"].lower()))
            overlap  = len(q_tokens & d_tokens)
            if overlap > 0:
                scored.append((overlap, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"text": d["text"], "source": d["source"], "score": round(s / max(len(q_tokens), 1), 3)}
            for s, d in scored[:top_k]
        ]

    # ── 私有：Prompt 构建 ─────────────────────────────────────────

    def _build_rag_prompt(
        self,
        user_query:    str,
        chip_name:     str,
        chip_type:     str,
        context_text:  str,
        skeleton_code: str,
        extra_context: str,
    ) -> str:
        skeleton_section = (
            f"\n【基础骨架代码（请在此基础上优化）】\n```cpp\n{skeleton_code}\n```\n"
            if skeleton_code else ""
        )
        return f"""你是 STS8200S 测试平台的资深 ATE 测试工程师，精通 STS8200S 函数编程手册。
根据【手册参考片段】，为芯片 {chip_name}（类型: {chip_type}）生成符合 STS8200S 规范的 C++ 测试代码。

【工程师需求】
{user_query}

【STS8200S 手册参考片段（检索自编程手册）】
{context_text}
{extra_context}
{skeleton_section}
【生成要求】
1. 代码必须包含 DUT_API void HardWareCfg() 和 DUT_API void InitBeforeTestFlow()
2. 每个测试函数必须调用 StsGetParam() 获取限值，调用 SetTestResult() 上报结果
3. 根据手册片段中的 API 名称和参数格式，精确调用 FOVI/PMU/DIO 相关函数
4. 添加详细的中文注释，说明每步操作目的和对应的手册章节
5. 如果手册片段包含量程常量（如 FOVI_10V），直接使用，不要自造常量

只输出完整 C++ 代码，用 ```cpp ... ``` 包裹，不要任何解释文字。"""

    def _format_context(self, chunks: List[Dict]) -> str:
        if not chunks:
            return "（未检索到相关手册内容，将基于通用 STS8200S 规范生成）"
        parts = []
        for i, c in enumerate(chunks, 1):
            score_str = f"相关度 {c['score']:.2f}" if "score" in c else ""
            parts.append(f"[片段{i} | {c.get('source','')} {score_str}]\n{c['text']}")
        return "\n\n".join(parts)

    def _extract_code_block(self, raw: str) -> str:
        m = re.search(r"```(?:cpp|c\+\+)?\s*([\s\S]+?)```", raw, re.IGNORECASE)
        return m.group(1).strip() if m else raw

    def _get_llm_client(self) -> OpenAI:
        if self._client is None:
            http_client = httpx.Client(
                timeout=httpx.Timeout(connect=30, read=120, write=30, pool=30),
                verify=settings.SSL_VERIFY,
            )
            self._client = OpenAI(
                api_key     = settings.DEEPSEEK_API_KEY,
                base_url    = settings.DEEPSEEK_BASE_URL,
                http_client = http_client,
                timeout     = 120.0,
            )
        return self._client


# ── 全局单例 ──────────────────────────────────────────────────────
_rag_service: Optional[RAGService] = None

def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service


# ── STS8200S 内置知识库（无 PDF 时使用）────────────────────────────
STS8200S_BUILTIN_KNOWLEDGE = [
    {
        "title": "FOVI 强迫电压测量电流",
        "content": """UserFOVI(ch, range, forceV, clampI) — 强迫电压，测量电流
range 可选：FOVI_1V / FOVI_2V / FOVI_5V / FOVI_10V / FOVI_20V / FOVI_50V
电流量程：FOVI_1mA / FOVI_10mA / FOVI_100mA / FOVI_1A
示例：UserFOVI(0, FOVI_10V, 5.0, 0.1) — 强迫5V，允许最大100mA
测量结果：GetFOVI_Meas(ch) 返回 double 类型电流值(A)
VIH 测试：设定 FOVI 输出高电平电压，读回芯片引脚电压确认逻辑响应"""
    },
    {
        "title": "QTMU 精密电流测量",
        "content": """UserQTMU(ch, range, forceV) — 精密小电流测量
range 可选：QTMU_1uA / QTMU_10uA / QTMU_100uA / QTMU_1mA / QTMU_10mA
典型应用：Iq 静态电流、漏电流 (nA~μA 级)
示例：UserQTMU(0, QTMU_1mA, 0.0) — 强迫0V，测量漏电流
GetQTMU_Meas(ch) 返回电流测量值(A)"""
    },
    {
        "title": "DIO 数字输入输出",
        "content": """SetDIO(ch, level, state) — 设置 DIO 通道电平
ch：DIO 通道号(0-23)，level：电平值(V)，state：IN/OUT
RunVector(label) — 运行指定向量文件中的测试序列
GetDIO_Fail() — 获取失败引脚位图
DIO 通道支持：VIH/VIL 编程范围 -2V ~ +7V（TTL/CMOS 兼容）
功能测试(FUN)：RunVector("功能测试向量名") 执行完整功能序列"""
    },
    {
        "title": "StsGetParam 参数读取",
        "content": """CParam *param = StsGetParam(funcindex, "参数名")
funcindex：PGS 中定义的函数索引号
param->GetMin() — 读取下限值
param->GetMax() — 读取上限值
param->SetTestResult(measured, min, max) — 上报测试结果
CParam 自动判断 Pass/Fail 并记录到 bin 结果"""
    },
    {
        "title": "HardWareCfg 硬件配置",
        "content": """DUT_API void HardWareCfg() {
    STSSetHardwareCheck(FALSE);  // 关闭硬件安全检查（调试时可打开）
    // 初始化 FOVI 通道分组：数字类芯片通常
    // FVI0 = VCC 电源，FVI1~FVI3 = 测量用
}
DUT_API void InitBeforeTestFlow() {
    // 每个 DUT 测试前的初始化序列
    // 例如复位芯片、设置初始电压
}"""
    },
    {
        "title": "LDO 压降测试流程",
        "content": """LDO Dropout（压降）测试步骤：
1. UserFOVI(FVI0, FOVI_10V, Vin_start, Ilimit) — 施加输入电压
2. UserFOVI(FVI1, FOVI_1A, Iload, Vlimit) — 施加负载电流（电流源模式）
3. 逐步降低 Vin：while(Vout > Vout_nom * 0.99) { Vin -= 0.1; }
4. 记录 Dropout = Vin - Vout 最小压差
脉冲模式：UserFOVI_Pulse(ch, range, forceV, pulse_us) — 短脉冲避免器件过热"""
    },
    {
        "title": "CON 连通性测试",
        "content": """连通性测试（CON）检查接触电阻和断路：
DUT_API int CON_Test(short funcindex, LPCTSTR funclabel) {
    CParam *param = StsGetParam(funcindex, "CON");
    // 所有引脚强迫 0.1V 测量电流，接触良好时约 1-5mA
    for(int ch = 0; ch < PIN_COUNT; ch++) {
        UserFOVI(ch, FOVI_1V, 0.1, 0.05);  // 强迫100mV, 限流50mA
        double i = GetFOVI_Meas(ch);
        if(fabs(i) < 0.001) {  // 小于1mA认为断路
            param->SetPinFail(ch);
        }
    }
    param->SetTestResult(0, 0, 0);
    return 0;
}"""
    },
    {
        "title": "ACSM 时序测量",
        "content": """ACSM 模块用于测量传播延迟、上升/下降时间：
SetACSM_Threshold(ch, vth) — 设置电平阈值
RunACSM(pattern) — 运行时序测量序列
GetACSM_tPHL(ch) — 获取高到低传播延迟(ns)
GetACSM_tPLH(ch) — 获取低到高传播延迟(ns)
GetACSM_Tr(ch) — 上升时间，GetACSM_Tf(ch) — 下降时间
测量分辨率：1ns，最大范围：100μs"""
    },
]

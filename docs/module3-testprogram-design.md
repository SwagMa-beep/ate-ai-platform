# Module 3 Design (TestProgram / Codegen) - Code-Aligned Version

## 1. Scope

Module 3 in the current codebase has two related paths:

1. Active production path: `POST /api/v1/codegen/generate`
2. Skeleton path in code: `backend/app/api/v1/testprogram.py` (implemented but not mounted in `main.py`)

This document describes the active path first, and marks the skeleton path as pending integration.

## 2. Active API Contract (`/api/v1/codegen`)

### 2.1 Generate

Endpoint:

`POST /api/v1/codegen/generate`

Request fields:

1. `chip_name` (string)
2. `chip_type` (`digital | ldo | custom`)
3. `test_items` (string array)
4. `user_prompt` (string)
5. Optional pin and electrical context:
`pin_names`, `input_pins`, `output_pins`, `vcc`, `vout`, `ldo_out_pin`, `load_ma`

Response core fields:

1. `code`
2. `filename`
3. `lines`
4. `functions`
5. `static_analysis`
6. `retrieved_chunks` (when RAG is used)

### 2.2 Templates

Endpoint:

`GET /api/v1/codegen/templates`

Returns supported test-item templates for digital and LDO scenarios.

## 3. Generation Pipeline

### 3.1 Step 1 - Template skeleton

The service builds a compile-oriented C++ skeleton from built-in template fragments:

1. File header and STS includes
2. Pin declarations
3. Lifecycle callbacks (`HardWareCfg`, `InitBeforeTestFlow`, etc.)
4. One function per selected test item

### 3.2 Step 2 - Optional RAG enhancement

If user prompt exists and RAG is ready:

1. Retrieve STS manual chunks from vector store
2. Inject retrieved context into prompt
3. Ask LLM to generate improved code

RAG backend behavior:

1. Preferred: `ChromaDB + embeddings`
2. Fallback: keyword/TF-IDF style retrieval when ChromaDB is unavailable

### 3.3 Step 3 - AI polish fallback

If RAG is unavailable or fails, service falls back to template + LLM polish mode.

### 3.4 Step 4 - Static analysis

Generated code is validated by `CodeValidator`; analysis score and issues are returned with code output.

## 4. Current Input/Output Dependencies

### 4.1 Required runtime dependency

1. DeepSeek-compatible API key (`DEEPSEEK_API_KEY`) for LLM enhancement

### 4.2 Optional dependency

1. RAG index availability (manual text or PDF-built index)

### 4.3 Generated artifact type

Current active module returns generated code in API response JSON.  
File-system project export for full module-3 bundle is handled by the separate skeleton service path and can be integrated later.

## 5. Skeleton Service Path (`/api/v1/testprogram`) Status

The following code exists:

1. `POST /generate`
2. `GET /requirements`
3. `TestProgramService`-based folder/file generation flow

But this router is not currently included in `backend/app/main.py`, so it is not active in running app routes.

## 6. Recommended Next Iteration

1. Mount `testprogram` router into main app, or remove duplicate path to avoid confusion
2. Unify module-3 contract around one public endpoint family
3. Add regression tests for template rendering + RAG/fallback branches
4. Expose explicit response flags:
`rag_used`, `fallback_used`, `validator_passed`


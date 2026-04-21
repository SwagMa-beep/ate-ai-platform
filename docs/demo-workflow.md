# Demo Workflow

This document describes a repeatable demo path for ATE-AI-Platform. It is designed for project reviews, interviews, and quick local verification.

## Demo Goal

Show the full flow from a chip datasheet to ATE development artifacts:

1. Upload a Datasheet PDF.
2. Extract TestPlan parameters and pin definitions.
3. Download Excel/JSON outputs.
4. Generate STS8200S resource mapping and schematic files.
5. Generate C++ test code.
6. Run yield diagnosis simulation.

## Recommended Demo Files

| File | Type | Suggested Use |
| --- | --- | --- |
| `data/raw/Renesas-HD74LS00P.pdf` | Digital logic chip | Main demo. Smaller PDF, faster to upload and process. |
| `data/raw/ADI-AD780.pdf` | Analog reference chip | Optional second demo for analog parameter extraction. |

For the first demo, use:

```text
data/raw/Renesas-HD74LS00P.pdf
```

## 1. Start Backend

From the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open the health check:

```text
http://localhost:8000/health
```

Expected result:

- `status` is `success`
- `data.status` is `healthy`
- `api_configured` is `true` if `DEEPSEEK_API_KEY` is configured

## 2. Start Frontend

Open a second terminal:

```powershell
cd apps
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

## 3. Run TestPlan Extraction

In the frontend:

1. Open the `数据手册提取` page.
2. Upload `data/raw/Renesas-HD74LS00P.pdf`.
3. Wait for upload and extraction to finish.
4. Review the result panel.

Expected result:

- The page shows the detected chip name.
- Parameter statistics are displayed.
- Pin definitions are listed if the datasheet contains extractable pin information.
- STS8200S compatibility information is shown.
- Excel and JSON download buttons are available.

Generated outputs are stored under:

```text
data/processed/
```

Download and inspect:

- `TestPlan.xlsx`
- `TestPlan.json`

## 4. Generate Resource Mapping

After TestPlan extraction finishes:

1. Open the `资源映射 & 原理图` page.
2. Confirm that the previous `file_id` is detected automatically.
3. Leave `双工位模式` disabled for the digital logic demo.
4. Click `生成资源映射`.

Expected result:

- The system displays chip type, adapter model, pin count, and PGS item count.
- Schematic SVG preview is displayed if SVG loading succeeds.
- Download buttons are available for:
  - Resource Map Excel
  - Schematic SVG
  - BOM Excel

Generated outputs are stored under:

```text
data/processed/
```

## 5. Generate STS8200S Test Code

Open the `AI 测试代码生成` page.

For the digital demo:

| Field | Suggested Value |
| --- | --- |
| 芯片类型 | 数字逻辑芯片 |
| 芯片型号 | `HD74LS00P` |
| VCC | `5.0` |
| 测试项目 | `CON`, `FUN`, `VIH`, `VIL` |
| 补充说明 | `Standard TTL logic chip, generate STS8200S test flow with clear comments.` |

Click `生成测试代码`.

Expected result:

- A C++ file is generated in the editor.
- The generated code contains STS8200S lifecycle hooks such as `HardWareCfg` and `InitBeforeTestFlow`.
- The generated code contains test functions such as `CON`, `FUN`, `VIH`, or `VIL`.
- Code statistics and static validation results are displayed.
- The `.cpp` file can be copied or downloaded.

If the RAG knowledge base is ready, the page also shows retrieved STS8200S reference chunks.

## 6. Run Yield Diagnosis

Open the `失效源分析` page.

The page runs diagnosis automatically on first load. You can also click:

```text
运行全量诊断
```

Expected result:

- VI waveform is displayed.
- FTY and yield metrics are updated.
- Anomaly events are listed when simulated anomalies are detected.
- The diagnosis log can be exported as JSON.

This module uses simulated production waveform data and is intended to demonstrate the diagnosis workflow and frontend visualization.

## 7. Optional CLI Demo

The same TestPlan extraction can be shown without the frontend:

```powershell
cd backend
python cli.py --pdf ../data/raw/Renesas-HD74LS00P.pdf --workers 3
```

Expected result:

- The CLI prints extraction statistics.
- Excel and JSON files are written to `data/processed/`.

## 8. Verification Commands

Before presenting the project, run:

```powershell
# Backend unit tests
python -m pytest backend/tests -q

# Backend syntax check
python -m compileall -q backend/app

# Frontend build
cd apps
npm run build
```

Current expected test shape:

```text
9 passed, 2 skipped
```

The skipped tests are manual integration workflow tests. To run them, start the backend service and set:

```powershell
$env:RUN_INTEGRATION_TESTS="1"
python -m pytest backend/tests/test_full_workflow.py -q
```

## Demo Talking Points

- The project is not a generic chatbot. It targets a concrete ATE test-development workflow.
- The backend is modular: extraction, validation, resource mapping, code generation, RAG, and diagnosis are separated.
- The system has deterministic fallback paths where possible, such as template-based code generation and TF-IDF retrieval fallback.
- Generated artifacts are reviewable by engineers: Excel, JSON, SVG, BOM, and C++ source code.
- Unit tests cover core local logic without requiring API keys or external services.

## Known Demo Notes

- LLM extraction requires a valid `DEEPSEEK_API_KEY`.
- Generated code and mappings are engineering drafts and should be reviewed before real ATE hardware use.
- RAG can run with an optional ChromaDB backend; otherwise the service falls back to simpler retrieval.
- The yield diagnosis page uses simulated data for demonstration.

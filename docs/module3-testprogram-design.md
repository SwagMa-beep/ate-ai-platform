# Module 3 Design (TestProgram Generation)

## 1. Goal

Module 3 generates STS8200S test program artifacts from Module 1 and Module 2 outputs.
The generator is template-driven and produces editable source code plus metadata files.

## 2. Inputs

### 2.1 Required input (from Module 1)

- `*{file_id}*TestPlan.json`

Required fields from the JSON:

- `chip_name`
- `chip_type`
- `pin_definitions`
- `parameters`
- `statistics`

### 2.2 Optional input (from Module 2)

- `*ResourceMap.xlsx`
- `*BOM.xlsx`
- `*Schematic.svg`

If no explicit resource-map prefix is provided, the latest Module 2 artifacts are used.

## 3. Outputs

Module 3 creates one generation folder:

- `data/processed/generated_programs/{file_id}_{timestamp}_{chip_name}/`

Generated files:

- `manifest.json`
- `codegen_plan.json`
- `source/{chip_name}.cpp`
- `source/test.cpp`
- `README.txt`

Notes:

- The generated code is a compile-ready skeleton for manual refinement.
- `.pgs` and `.vecdio` are currently referenced in the plan and are produced in later iterations.

## 4. Constraints from Contest Materials

- STS software version baseline: `STS8200S VerP1.1 Build 20251201`
- PGS editor baseline: `3.0`
- DLL hook signatures must remain stable:
  - `UserLoad`
  - `UserInitAfterLoad`
  - `UserExit`
  - `OnSot`
  - `BinOutDut`
  - `OnNewLot`
  - `OnWaferEnd`

## 5. Generation Strategy

### 5.1 Function list extraction

From `parameters`, derive a deduplicated function list by `param_name`.
Normalize names to uppercase and filter invalid identifiers.

### 5.2 Source skeleton generation

- `source/{chip_name}.cpp`
  - DLL entry + fixed hook functions.
- `source/test.cpp`
  - `HardWareCfg`, `InitBeforeTestFlow`, `InitAfterTestFlow`, `SetupFailSite`
  - one test stub per generated function name:
    - `DUT_API int <FUNC>(short funcindex, LPCTSTR funclabel)`
    - resolve param with `StsGetParam(funcindex, "<FUNC>")`

### 5.3 Plan and traceability

- `manifest.json`: exact input files and output files.
- `codegen_plan.json`: chip metadata, functions, and source trace.

## 6. API Contract (current)

Endpoint:

- `POST /api/v1/testprogram/generate`

Request body:

- `file_id` (required)
- `resource_prefix` (optional)
- `generator_mode` (default `skeleton`)

Response:

- generation id
- chip metadata
- input artifacts
- generated file list
- output directory

## 7. Future Extensions

- Generate `.pgs` from Module 1 limits + Module 2 resource mapping.
- Generate `.vecdio` for digital devices from pin grouping and function vectors.
- Emit project files (`.vcxproj/.sln`) from templates.
- Add per-chip strategy plugins for digital, LDO, EEPROM, multisite.

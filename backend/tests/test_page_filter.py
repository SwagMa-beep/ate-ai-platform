from app.services.testplan_service import TestPlanService as PlanService
from app.models.testplan import DCParam


def test_page_filter_keeps_electrical_and_pin_pages():
    chunks = [
        {
            "page": 1,
            "content": "To our customers. Legal disclaimer. Subject to change.",
        },
        {
            "page": 2,
            "content": (
                "Pin Arrangement\n"
                "1A 1 14 VCC\n"
                "1B 2 13 4B\n"
                "GND 7 8 3Y\n"
            ),
        },
        {
            "page": 3,
            "content": (
                "Electrical Characteristics\n"
                "Item Symbol min. typ. max. Unit Condition\n"
                "Input voltage VIH 2.0 V\n"
                "Output voltage VOH 2.7 V\n"
            ),
        },
        {
            "page": 4,
            "content": (
                "Package Dimensions\n"
                "JEITA Package Code RENESAS Code Previous Code MASS[Typ.]\n"
                "Reference Dimension in Millimeters Symbol Min Nom Max\n"
            ),
        },
    ]

    filtered = PlanService._filter_and_batch_chunks(chunks)

    assert [chunk["page"] for chunk in filtered] == ["2", "3"]
    assert "Pin Arrangement" in filtered[0]["content"]
    assert "Electrical Characteristics" in filtered[1]["content"]
    assert all("Package Dimensions" not in chunk["content"] for chunk in filtered)


def test_compact_chunk_content_prefers_extracted_table_copy():
    content = """HD74LS00
Electrical Characteristics
(Ta = -20 to +75 C)
Item Symbol min. typ. max. Unit Condition
Input voltage VIH 2.0 -- -- V
Output voltage VOH 2.7 -- -- V
Switching Characteristics
Note: VCC = 5 V
""" + ("filler\n" * 80) + """Item\tSymbol\tmin.\ttyp.\tmax.\tUnit\tCondition
Input voltage\tVIH\t2.0\t--\t--\tV
Output voltage\tVOH\t2.7\t--\t--\tV
"""

    compacted = PlanService._compact_chunk_content(content)

    assert len(compacted) < len(content)
    assert "Electrical Characteristics" in compacted
    assert "Switching Characteristics" in compacted
    assert "Item\tSymbol\tmin." in compacted
    assert "filler" not in compacted


def test_local_pin_extractor_reads_two_column_pin_arrangement():
    chunks = [
        {
            "page": "3",
            "content": """[Page 3]
Pin Arrangement
1A 1 14 V
CC
1B 2 13 4B
1Y 3 12 4A
GND 7 8 3Y
(Top view)
""",
        }
    ]

    pins = PlanService._extract_pin_definitions_from_chunks(chunks)

    assert [(pin.pin_no, pin.pin_name, pin.direction) for pin in pins] == [
        (1, "1A", "IN"),
        (2, "1B", "IN"),
        (3, "1Y", "OUT"),
        (7, "GND", "GND"),
        (8, "3Y", "OUT"),
        (12, "4A", "IN"),
        (13, "4B", "IN"),
        (14, "VCC", "PWR"),
    ]


def test_drop_local_pin_chunks_keeps_parameter_pages():
    chunks = [
        {"page": "3", "content": "Pin Arrangement\n1A 1 14 V\nCC"},
        {"page": "5", "content": "Electrical Characteristics\nItem Symbol min typ max Unit"},
    ]
    pins = PlanService._extract_pin_definitions_from_chunks(chunks)

    llm_chunks = PlanService._drop_local_pin_chunks(chunks, pins)

    assert [chunk["page"] for chunk in llm_chunks] == ["5"]


def test_local_pin_extractor_handles_ad780_visual_pin_configuration():
    chunks = [
        {
            "page": "4",
            "content": (
                "Data Sheet AD780\n"
                "Figure 2. Pin Configuration, 8-Lead PDIP and SOIC Packages\n"
                "THERMAL RESISTANCE\n"
            ),
        }
    ]

    pins = PlanService._extract_pin_definitions_from_chunks(chunks)

    assert [(pin.pin_no, pin.pin_name, pin.direction) for pin in pins] == [
        (1, "DNC", "NC"),
        (2, "+VIN", "PWR"),
        (3, "TEMP", "OUT"),
        (4, "GND", "GND"),
        (5, "TRIM", "IN"),
        (6, "VOUT", "OUT"),
        (7, "DNC", "NC"),
        (8, "2.5/3.0 O/P SELECT", "IN"),
    ]


def test_local_param_extractor_fills_temperature_and_ac_timing():
    chunks = [
        {
            "page": "4",
            "content": """[Page 4]
Absolute Maximum Ratings
Item\tSymbol\tRatings\tUnit
Supply voltage\tV Note
CC\t7\tV
Input voltage\tV
IN\t7\tV
Power dissipation\tP
T\t400\tmW
Storage temperature\tTstg\t-65 to +150\t°C
Recommended Operating Conditions
Item\tSymbol\tMin\tTyp\tMax\tUnit
Operating temperature\tTopr\t-20\t25\t75\t°C
""",
        },
        {
            "page": "5",
            "content": """[Page 5]
Switching Characteristics
Item\tSymbol\tmin.\ttyp.\tmax.\tUnit\tCondition
Propagation delay time\tt
PLH\t—\t9\t15\tns\tC = 15 pF, R = 2 kΩ
\tt
PHL\t—\t10\t15\tns
""",
        },
    ]

    params = PlanService._extract_local_params_from_chunks(chunks, "DIGITAL_74")
    indexed = {(p.category, p.param_name): p for p in params}

    assert indexed[("B", "VCC")].max_val == 7.0
    assert indexed[("B", "VIN")].max_val == 7.0
    assert indexed[("B", "PT")].max_val == 400.0
    assert indexed[("B", "PT")].unit == "mW"
    assert indexed[("B", "TSTG")].min_val == -65.0
    assert indexed[("B", "TSTG")].max_val == 150.0
    assert indexed[("C", "TOPR")].min_val == -20.0
    assert indexed[("C", "TOPR")].typ_val == 25.0
    assert indexed[("C", "TOPR")].max_val == 75.0
    assert indexed[("A", "tPLH")].typ_val == 9.0
    assert indexed[("A", "tPLH")].max_val == 15.0
    assert indexed[("A", "tPLH")].test_scenario == "DIGITAL_AC"
    assert indexed[("A", "tPHL")].typ_val == 10.0
    assert indexed[("A", "tPHL")].sts_test_function == "ACSM_Test"


def test_merge_missing_local_params_does_not_duplicate_existing_llm_params():
    llm_params = [
        DCParam(
            param_name="tPLH",
            category="A",
            test_scenario="DIGITAL_AC",
            typ_val=9.0,
            max_val=15.0,
            unit="ns",
        )
    ]
    local_params = [
        DCParam(
            param_name="tPLH",
            category="A",
            test_scenario="DIGITAL_AC",
            typ_val=9.0,
            max_val=15.0,
            unit="ns",
        ),
        DCParam(
            param_name="TOPR",
            category="C",
            test_scenario="DIGITAL_DC",
            min_val=-20.0,
            typ_val=25.0,
            max_val=75.0,
            unit="C",
        ),
    ]

    merged = PlanService._merge_missing_local_params(llm_params, local_params)

    assert [(p.category, p.param_name) for p in merged] == [("A", "tPLH"), ("C", "TOPR")]

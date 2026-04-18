"""
SVG原理图生成器 - 模块二
生成芯片引脚 ↔ STS8200S资源连接示意图
"""
from typing import List, Dict, Tuple
from pathlib import Path
from app.models.resource_map import ResourceMapping
from app.utils.logger import setup_logger

logger = setup_logger()

# 颜色定义（按资源类型）
RESOURCE_COLORS = {
    "FH_SH": "#E74C3C",   # 红色  - VI源（模拟）
    "DIO":   "#3498DB",   # 蓝色  - 数字IO
    "CBIT":  "#F39C12",   # 橙色  - 继电器控制
    "TMU":   "#9B59B6",   # 紫色  - 时序测量
    "VDD":   "#E91E63",   # 粉红  - 电源
    "GND":   "#607D8B",   # 灰蓝  - 地
    "NC":    "#BDC3C7",   # 浅灰  - 未连接
}

RESOURCE_LABELS = {
    "FH_SH": "VI源(FOVI)",
    "DIO":   "数字IO",
    "CBIT":  "继电器控制",
    "TMU":   "时序测量",
    "VDD":   "电源",
    "GND":   "地",
    "NC":    "未连接",
}


class SVGGenerator:
    """SVG原理图生成器"""

    # 布局参数
    CHIP_X        = 300
    CHIP_Y        = 80
    CHIP_W        = 200
    PIN_HEIGHT    = 36
    PIN_FONT      = 13
    STS_X_LEFT    = 30
    STS_X_RIGHT   = 560
    CONN_OFFSET   = 140

    def generate(
        self,
        chip_name: str,
        chip_type: str,
        mappings: List[ResourceMapping],
        output_path: str
    ) -> str:
        """
        生成SVG文件

        Args:
            chip_name   : 芯片型号
            chip_type   : 芯片类型
            mappings    : 资源映射列表
            output_path : 输出SVG文件路径

        Returns:
            SVG文件绝对路径
        """
        # 过滤掉GND和NC，但保留用于显示
        valid_maps = [m for m in mappings if m.resource_type != "NC"]
        all_maps   = mappings

        pin_count  = len(all_maps)
        chip_h     = max(pin_count * self.PIN_HEIGHT + 60, 200)
        svg_h      = chip_h + 160
        svg_w      = 750

        lines = []
        lines.append(self._svg_header(svg_w, svg_h))
        lines.append(self._defs())
        lines.append(self._title_bar(
            svg_w, chip_name, chip_type, len(valid_maps)
        ))
        lines.append(self._chip_body(
            self.CHIP_X, self.CHIP_Y, self.CHIP_W,
            chip_h, chip_name
        ))
        lines.append(self._sts_body(
            self.STS_X_LEFT, self.CHIP_Y, chip_h
        ))
        lines.append(self._sts_body_right(
            self.STS_X_RIGHT, self.CHIP_Y, chip_h
        ))
        lines.append(self._legend(svg_w, svg_h))

        # 绘制每个引脚和连线
        for idx, m in enumerate(all_maps):
            y_pin = self.CHIP_Y + 40 + idx * self.PIN_HEIGHT
            lines.append(self._draw_pin_row(m, y_pin, svg_w))

        lines.append("</svg>")

        svg_content = "\n".join(lines)

        # 写入文件
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        logger.success(f"✅ SVG已生成: {output_path}")
        return str(Path(output_path).absolute())

    # ── SVG组件 ──────────────────────────────────────────────

    def _svg_header(self, w: int, h: int) -> str:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{w}" height="{h}" '
            f'style="font-family:Arial,sans-serif;background:#F8F9FA;">'
        )

    def _defs(self) -> str:
        return """<defs>
  <marker id="arrow" markerWidth="8" markerHeight="8"
          refX="6" refY="3" orient="auto">
    <path d="M0,0 L0,6 L8,3 z" fill="#555"/>
  </marker>
  <filter id="shadow">
    <feDropShadow dx="2" dy="2" stdDeviation="2" flood-opacity="0.15"/>
  </filter>
</defs>"""

    def _title_bar(
        self, w: int, chip_name: str, chip_type: str, conn_count: int
    ) -> str:
        return (
            f'<rect x="0" y="0" width="{w}" height="50" fill="#2C3E50"/>'
            f'<text x="20" y="32" fill="white" '
            f'font-size="18" font-weight="bold">'
            f'STS8200S 资源映射原理图 — {chip_name} [{chip_type}]'
            f'</text>'
            f'<text x="{w-20}" y="32" fill="#BDC3C7" '
            f'font-size="12" text-anchor="end">'
            f'有效连接: {conn_count}路'
            f'</text>'
        )

    def _chip_body(
        self, x: int, y: int, w: int, h: int, name: str
    ) -> str:
        return (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
            f'rx="8" fill="#ECF0F1" stroke="#2C3E50" '
            f'stroke-width="2.5" filter="url(#shadow)"/>'
            f'<text x="{x + w//2}" y="{y + 22}" '
            f'text-anchor="middle" font-size="14" '
            f'font-weight="bold" fill="#2C3E50">{name}</text>'
            f'<text x="{x + w//2}" y="{y + 38}" '
            f'text-anchor="middle" font-size="10" fill="#7F8C8D">DUT</text>'
        )

    def _sts_body(self, x: int, y: int, h: int) -> str:
        return (
            f'<rect x="{x}" y="{y}" width="120" height="{h}" '
            f'rx="8" fill="#EBF5FB" stroke="#2980B9" '
            f'stroke-width="2" filter="url(#shadow)"/>'
            f'<text x="{x+60}" y="{y+20}" text-anchor="middle" '
            f'font-size="11" font-weight="bold" fill="#2980B9">'
            f'STS8200S</text>'
            f'<text x="{x+60}" y="{y+35}" text-anchor="middle" '
            f'font-size="9" fill="#5D6D7E">FOVI/CBIT/TMU</text>'
        )

    def _sts_body_right(self, x: int, y: int, h: int) -> str:
        return (
            f'<rect x="{x}" y="{y}" width="120" height="{h}" '
            f'rx="8" fill="#EBF5FB" stroke="#2980B9" '
            f'stroke-width="2" filter="url(#shadow)"/>'
            f'<text x="{x+60}" y="{y+20}" text-anchor="middle" '
            f'font-size="11" font-weight="bold" fill="#2980B9">'
            f'STS8200S</text>'
            f'<text x="{x+60}" y="{y+35}" text-anchor="middle" '
            f'font-size="9" fill="#5D6D7E">DIO</text>'
        )

    def _draw_pin_row(
        self, m: ResourceMapping, y: int, svg_w: int
    ) -> str:
        color    = RESOURCE_COLORS.get(m.resource_type, "#BDC3C7")
        chip_lx  = self.CHIP_X               # 芯片左边X
        chip_rx  = self.CHIP_X + self.CHIP_W # 芯片右边X
        sts_lx   = self.STS_X_LEFT + 120     # STS左侧右端
        sts_rx   = self.STS_X_RIGHT           # STS右侧左端
        cy       = y + self.PIN_HEIGHT // 2

        parts = []

        # 引脚标签（芯片左侧/右侧交替）
        is_right = m.resource_type == "DIO"

        if not is_right:
            # 左侧引脚
            parts.append(
                f'<text x="{chip_lx - 8}" y="{cy + 4}" '
                f'text-anchor="end" font-size="{self.PIN_FONT}" '
                f'fill="#2C3E50">'
                f'P{m.pin_no} {m.pin_name}</text>'
            )
            # 引脚连接点
            parts.append(
                f'<circle cx="{chip_lx}" cy="{cy}" r="4" '
                f'fill="{color}" stroke="white" stroke-width="1.5"/>'
            )
            # 连线（芯片左 → STS左侧）
            parts.append(
                f'<line x1="{chip_lx}" y1="{cy}" '
                f'x2="{sts_lx}" y2="{cy}" '
                f'stroke="{color}" stroke-width="2" '
                f'stroke-dasharray="{"" if m.resource_type != "NC" else "4,4"}"/>'
            )
            # STS资源标签
            parts.append(
                f'<text x="{sts_lx - 8}" y="{cy + 4}" '
                f'text-anchor="end" font-size="11" fill="{color}" '
                f'font-weight="bold">{m.sts_resource}</text>'
            )
        else:
            # 右侧引脚（DIO通道）
            parts.append(
                f'<text x="{chip_rx + 8}" y="{cy + 4}" '
                f'text-anchor="start" font-size="{self.PIN_FONT}" '
                f'fill="#2C3E50">'
                f'P{m.pin_no} {m.pin_name}</text>'
            )
            parts.append(
                f'<circle cx="{chip_rx}" cy="{cy}" r="4" '
                f'fill="{color}" stroke="white" stroke-width="1.5"/>'
            )
            parts.append(
                f'<line x1="{chip_rx}" y1="{cy}" '
                f'x2="{sts_rx}" y2="{cy}" '
                f'stroke="{color}" stroke-width="2"/>'
            )
            parts.append(
                f'<text x="{sts_rx + 8}" y="{cy + 4}" '
                f'text-anchor="start" font-size="11" '
                f'fill="{color}" font-weight="bold">'
                f'{m.sts_resource}</text>'
            )

        # 悬停提示
        parts.append(
            f'<title>{m.pin_name}: {m.sts_resource} | '
            f'{m.force_mode}/{m.measure_mode} | {m.notes}</title>'
        )

        return "\n".join(parts)

    def _legend(self, svg_w: int, svg_h: int) -> str:
        """图例"""
        legend_y = svg_h - 90
        parts    = [
            f'<rect x="10" y="{legend_y}" width="{svg_w-20}" '
            f'height="80" rx="6" fill="white" '
            f'stroke="#DEE2E6" stroke-width="1"/>',
            f'<text x="20" y="{legend_y+18}" font-size="12" '
            f'font-weight="bold" fill="#2C3E50">图例</text>',
        ]
        x_offset = 20
        for rtype, color in RESOURCE_COLORS.items():
            label = RESOURCE_LABELS.get(rtype, rtype)
            parts.append(
                f'<rect x="{x_offset}" y="{legend_y+25}" '
                f'width="14" height="14" rx="3" fill="{color}"/>'
            )
            parts.append(
                f'<text x="{x_offset+18}" y="{legend_y+37}" '
                f'font-size="11" fill="#555">{label}</text>'
            )
            x_offset += 100
            if x_offset > svg_w - 60:
                x_offset  = 20
                legend_y += 20

        return "\n".join(parts)
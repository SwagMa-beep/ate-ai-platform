# FOVI100 force and measure patterns

适用场景：
- 模拟芯片电压/电流源与测量
- LDO、基准源、运放等参数测试
- AWG 激励与同步采样
- 多工位并行的模拟资源驱动

核心能力：
- 单板 8 通道，每 4 通道为一组浮动单元，共用一组 FL/SL
- 全四象限 force/measure
- 支持 Kelvin 四线连接
- 电压量程：±50V（最大输出 ±40V）、±20V、±10V、±5V、±2V、±1V
- 电流量程：±1A pulse、±100mA、±10mA、±1mA、±100uA、±10uA（仅测量）、±1uA（仅测量）
- 每通道可编程电压/电流 clamp
- 支持 16 工位并行和乒乓测试

Kelvin 连接要点：
- 每路由 FH、SH、FL、SL、GUARD 组成
- FORCE_H / FORCE_L 负责驱动电流
- SENSE_H / SENSE_L 负责采集电压
- GUARD 在 nA 级小电流或高阻测试时很重要，用来包围 force/sense 走线防漏电
- CH0~CH3 共用一个 FL/SL，CH4~CH7 共用另一个 FL/SL，做资源规划时必须考虑共用关系

常见编程流程：
1. `FOVI vin(0);` 定义逻辑通道
2. `StsSetModuleToSite(MD_FOVI, SITE_x, channel..., -1)` 绑定工位
3. `Init()` 或用系统统一初始化函数
4. `Set(mode, level, vrange, irange, relay)` 设定源模式和量程
5. 必要时 `SetClamp(...)`
6. `MeasureVI(sampleTimes, samplePeriod, measMode, ...)`
7. `GetMeasResult(site, MVRET/MIRET, sampleIndex)` 读回
8. 测试结束后回到安全输出

Clamp 使用规则：
- `SetClamp(percent_PFS, percent_NFS)` 设正负箝位占满量程百分比
- `SetClamp` 与当前模式相关，FV/FI 切换会清除箝位设置
- 切换模式后若还依赖保护，需要重新设置 clamp
- 没有特别需求时，先用较保守 clamp 防止过压过流

MeasureVI 使用建议：
- `MeasureVI(sampleTimes, samplePeriod)` 默认普通模式
- `MEAS_AWG` 模式只做采样设置，真正启动由 AWG 驱动
- 采样间隔最小 10us，采样点数范围 1~2048
- `GetMeasResult(..., TRIG_RESULT)` 可读 AWG 同步触发点

Group 模式：
- `GPFOVI("name", fovi0, fovi1, ...)` 可把多路 FOVI 组成一个 group
- group 适用于多工位并行和多引脚同步刺激/测量
- 在调用 group 的 `Set()` 前，所有成员通道的模式、量程、继电器状态必须一致
- 常见用途：
  - offset / OS 类多点同步采样
  - leakage 并行测量

工程建议：
- 低电流泄漏优先用 uA 档，并结合 GUARD / Kelvin 走线
- 高精度 VOUT 测量先检查是否应切到专用量程与 DMM，而不是默认高压大档
- FOVI 能同时量 V 和 I，获取结果时只需选 `MVRET` 或 `MIRET`
- 多工位并行时，优先考虑共用 FL/SL、group 一致性和 clamp 安全边界

常见风险：
- 模式切换后忘了重设 clamp
- 共用 FL/SL 的通道被当成完全独立资源使用
- leakage 测试没有 guard/Kelvin，导致板上漏电掩盖 DUT 电流
- group 内量程/继电器状态不一致，导致 group `Set()` 行为错误

# QTMU_PLUS measurement patterns

适用场景：
- 时间参数测量：rise time、fall time、delay、pulse width
- 周期信号测量：frequency、duty cycle
- 事件计数：非周期信号跳变计数、多个跳变时刻读取

板卡能力要点：
- 每模块最多 4 个时间测量通道，可配置为 2/4 通道模式
- 输入电压范围：±25V / ±5V
- 时间测量范围：10ns 到 40s
- 频率范围：0.1Hz 到 10MHz
- 分辨率：coarse 10ns，fine 65ps
- 支持 8 工位并行和乒乓测试

初始化与工位绑定：
- `QTMU_PLUS qtmu0(0)` 定义逻辑通道，通道号范围 0~7
- 先用 `StsSetModuleToSite(MD_QTMUPLUS, SITE_x, channel, -1)` 绑定工位
- 每次测试前先 `qtmu0.Init()`，清空内部寄存器并断开输出继电器

典型编程流程：
1. 绑定工位和逻辑通道
2. 根据被测信号选择 `SetStartInput()` / `SetStopInput()`
3. 设置触发阈值和边沿：
   - `SetStartTrigger(level, slope)`
   - `SetStopTrigger(level, slope)`
4. 选择输入源模式：
   - `QTMU_PLUS_SINGLE_SOURCE`
   - `QTMU_PLUS_DUAL_SOURCE`
5. `Connect()` 后延时稳定
6. 调用测量函数：
   - `MeasFreq(...)`
   - `MeasDutyCycle(...)`
   - `Meas(...)`
   - `SetSinglePulseMeas(...)` + `SinglePlsMeas(...)`
7. 用 `GetMeasureResult(site)` 或事件计数相关接口读回
8. `Disconnect()` 释放资源

频率与占空比建议：
- 测频前先设置输入阻抗、量程和滤波，如 `QTMU_PLUS_IMPEDANCE_1M`、`QTMU_PLUS_VRNG_5V`
- 周期信号默认采样多个周期取平均，测频和占空比更稳
- CHB 测量频率时，通常要切到 `DUAL_SOURCE` 并用 `ChannelSetup(QTMU_PLUS_CHA_STOP)`

时间测量建议：
- 周期信号可直接 `Meas()` 读 rise/fall/delay
- 非周期脉冲应用 `SetSinglePulseMeas()` / `SinglePlsMeas()`
- 触发门限应对应实际阈值电平，不要直接照搬满量程百分比

事件计数建议：
- 非周期信号先 `SetSinglePulseEventCounter(...)`
- 再 `SetTimeOut(...)` 后触发 `SinglePulseEventCounter()`
- 用 `GetEventCounterActiveCount(site)` 读有效跳变个数
- 多个时刻点可用 `GetEventCounterMeasureResult(site, sampleIndex)`

与 FOVI 配合的常见模式：
- 用 FOVI 或其他 VI 源制造激励信号
- QTMU 只负责精确时间/频率测量
- 非周期样例里常见 `VEN.Set(...)` 作为触发信号，再由 QTMU 读上升/下降时间

工程风险：
- 没有调用 `Init()`，容易沿用上一次触发/寄存器状态
- CHB 测试没有切 `DUAL_SOURCE`，可能读不到 stop 通道
- 触发阈值和量程不匹配，会导致误触发或无法触发
- 周期信号和单脉冲信号混用接口，结果会不稳定

调试建议：
- 先确认接入的是 CHA 还是 CHB，再选 start/stop 输入
- 先用较宽松量程和简单阈值跑通，再收紧门限
- 频率和 duty 测试先从 5~10 个周期平均开始
- 若读数跳变，优先排查滤波、门限、电平范围和触发边沿设置

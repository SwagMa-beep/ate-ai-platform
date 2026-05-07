# ADP7118A LDO dynamic patterns

器件定位：
- 高压低噪声 LDO
- 案例测试覆盖静态参数、动态扫描、启动时间、欠压阈值、使能阈值和限流

案例中的资源结构：
- `EN`, `VIN`, `GND`, `VOUT` 都由 FOVI 参与
- `VL`, `VH` 作为辅助源
- `QTMU_PLUS` 用于启动时间类测量
- `CBIT128` 用于不同路径切换

初始化模式：
- `InitBeforeTestFlow()` 同时拉起 `VL/VH/EN/VIN/GND/VOUT`
- `VOUT` 通常以 `FI` 模式作为负载端使用
- 这类 LDO 案例比普通数字器件更依赖“多源同时存在”

核心测试项模式：
- `VO`：在不同负载区间读取输出电压
- `LNR`：扫输入电压，算线性调整率
- `LDR`：扫输出负载，算负载调整率
- `VDO1 / VDO2`：通过触发点测输入输出压差
- `ICL`：限流阈值
- `TP`：启动时间
- `UVLO`：欠压阈值
- `ENT`：使能阈值
- `IGND`：接地电流

ADP7118A 案例最值得学的地方：
- 大量使用 `AWG + MEAS_AWG`
- 同时对 `EN / VIN / VOUT` 做同步测量
- 利用 `TRIG_RESULT` 读取触发点，再回溯 `VIN/VOUT` 的波形值

Dropout (`VDO`) 测试套路：
1. `VIN` 做向下斜坡扫描
2. `VOUT` 施加固定负载
3. `VOUT.SetMeasVTrig(4.5, TRIG_FALLING)` 设置触发条件
4. `STSAWGRunTriggerStop(...)`
5. 取 `TRIG_RESULT` 对应采样点
6. 读当时的 `VIN` 与 `VOUT`，差值即 dropout

LDO 动态测试工程建议：
- 先把 `EN` 固定在可工作的高电平，再扫描 `VIN` 或 `IOUT`
- 对 10mA 和 200mA 这类不同负载条件分开做知识化记录
- 用 `TRIG_RESULT` 比用固定 sample index 更稳，尤其在边界点测试里

QTMU 的角色：
- 不只是测数字延时，也可用于 LDO 启动时间这类模拟边沿问题
- 但前提是需要明确好 `EN`、`VOUT` 或其他节点的接入路径与触发门限

工程风险：
- FOVI 电流档、VIN 档、VOUT 负载档没有按场景切换，容易出现量程不匹配
- 动态测试没有明确稳定区间和触发条件，结果会漂
- 把 LNR/LDR/VDO 当成静态读点测试，会丢失边界行为

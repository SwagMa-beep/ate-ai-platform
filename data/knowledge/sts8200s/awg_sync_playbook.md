# AWG and synchronous measurement playbook

适用场景：
- LDO / 基准源 / 模拟芯片动态扫描
- 斜坡、电压阶跃、正弦/方波刺激
- AWG 输出与 FOVI/FPVI/QVM 同步测量
- AWG 与 DIO 协同执行

标准流程：
1. 构造波形数组 `pattern`
2. `AwgLoader()` 导入波形
3. 设置 VI 源初始状态
4. `AwgSelect()` 选择运行的波形区间
5. 设置 V/I trigger
6. `MeasureVI(MEAS_AWG)` 设置同步测量
7. `STSEnableAWG(...)`
8. `STSEnableMeas(...)`
9. `STSAWGRun()` 或 `STSAWGRunTriggerStop()`

常见建波函数：
- `STSAWGCreateSineData(...)`
- `STSAWGCreateTriangleData(...)`
- `STSAWGCreateSquareData(...)`
- `STSAWGCreateRampData(...)`

建波注意：
- AWG 波形首点和末点都要包含在数据中
- 所以数据长度通常 = 步进个数 + 1
- 例如 0V 到 180mV，step=1mV，长度应为 181，而不是 180

同步测量要点：
- `STSEnableAWG(...)` 前，必须先 `AwgLoader + AwgSelect`
- `STSEnableMeas(...)` 前，必须先 `MeasureVI(MEAS_AWG)`
- `STSEnableAWG` 支持 FPVI10 / FOVI100 对应源
- `STSEnableMeas` 支持 FPVI10 / FOVI100 / QVM 对应源

`STSAWGRun()` 行为建议：
- 默认不填 `delayTime`
- 这样系统会自动等待 AWG 扫描和同步测量中较长的那段时间
- 手工指定 delayTime 适合特别明确的时序安排，否则容易早退或空等

与前面知识条目的关系：
- FOVI/FPVI 的 `MeasureVI(MEAS_AWG)` 只是在做同步采样配置
- 真正的扫描启动点在 `STSAWGRun()`
- 想取跳变点，可结合 `GetMeasResult(..., TRIG_RESULT)`

工程建议：
- 动态测试先用较短波形和少量采样点跑通时序，再扩充波形长度
- AWG + 测量一起用时，先检查量程和 clamp，再考虑波形幅值
- 多源同步时，确保所有源在 `STSEnableAWG` 之前已完成 `AwgSelect`

常见风险：
- 没有 `MeasureVI(MEAS_AWG)` 就直接 `STSEnableMeas`
- 波形长度少 1，导致实际步进值与设计不一致
- 同步运行完成后，没有正确读取触发点或采样结果，误以为波形没跑

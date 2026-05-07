# HD74LS00P test strategy

器件类型：
- TTL 四路二输入 NAND 门
- 14 pin 封装
- 典型供电：5V TTL 体系

典型参数与 datasheet 关注点：
- `VIH >= 2.0V`
- `VIL <= 0.8V`
- `VOH >= 2.7V`
- `VOL <= 0.5V`
- `IOS`、`IIH`、`IIL`、`ICC`
- `VIK` 输入钳位
- 传播延时约 9~15ns 量级

项目案例里的测试项：
- `CON`
- `FUN`
- `VIH`
- `VIL`
- `VIK`
- `VOH`
- `VOL`
- `IOS`
- `II`
- `IIN`
- `ICC`

案例程序实现模式：
- `UserLoad()` 自动扫描并加载 vecdio
- `HardWareCfg()` 里关闭硬件检查
- `InitBeforeTestFlow()` 初始化 QTMU 和两路 VCC
- `CON` 用 PMU 恒流测压逐 pin 遍历
- `FUN` 用 DIO 跑 label 区间并保存 fail map
- `VIH` 用扫阈值方式逐步提高输入高电平
- `VIL` 用二分法寻找最小失效低电平
- `VIK` 用 `-18mA` 恒流测输入钳位电压

CON / FUN 的工程意义：
- `CON` 先快速确认物理电气连接和开短路风险
- `FUN` 通过向量执行确认 NAND 逻辑功能
- 只有 `FUN` 通过，后续阈值和电流类参数才更有解释意义

TTL 类器件的重点审查点：
- 5V 供电下的逻辑门限设置是否贴合 datasheet
- 向量 label 是否覆盖全部 NAND 真值组合
- 输出脚与输入脚分组是否清晰
- PMU 测试电流方向和量级是否合理

从案例里能直接复用的模式：
- 输入阈值搜索可以用渐进扫描或二分搜索
- `dio.SaveFailMap()` 适合快速定位功能测试失效向量
- `SetResultRemark()` 写 pin 名能大幅提升后续定位效率

工程建议：
- 对 TTL 门电路，先跑最小真值表，再扩充时序/边界测试
- `VIH/VIL` 搜索时注意步进和精度，不要过粗导致门限失真
- `VIK`、`IIH/IIL` 等电流类参数优先确认 PMU 量程和保护

常见风险：
- 向量通过但 pin remark 没写，后续难定位具体输入/输出脚
- 逻辑电平设得“能跑”但偏离 datasheet 门限
- CON 没先做就直接 FUN，导致把接触问题误判成逻辑问题

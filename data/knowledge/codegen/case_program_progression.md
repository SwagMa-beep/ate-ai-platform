# Case program progression patterns

目标：
- 帮助理解“模板 -> 具体器件程序”的演进方式
- 让工程师助手在回答代码生成/代码审查时更像看过真实程序

数字模板的起点：
- 最小模板通常只含：
  - `CON`
  - `FUN`
  - `UserLoad`
  - `InitBeforeTestFlow / InitAfterTestFlow`
- `AllPin_String / InputPin_String / OutputPin_String`
- `AllPin_Int / InputPin_Int / OutputPin_Int`

从模板到具体器件的演进：
1. 填 pin 名和 pin -> DIO 映射
2. 配置 `VCC1 / VCC2`
3. 补 `CON`
4. 补 `FUN`
5. 再加阈值、电流、电压类参数
6. 最后再加时序类（如 QTMU）

HD74LS00P 展示了数字器件的完整演进：
- 模板里的 `CON/FUN`
- 再加 `VIH/VIL`
- 再加 `VIK/VOH/VOL/IOS/II/IIN/ICC`
- 再加 `TPHL/TPLH`

AD780A 展示了模拟双工位演进：
- `HardWareCfg` 先做多工位绑定
- 资源以 `VIN / VOUT + CBIT` 为主
- 参数以 `VO/LNR/LDR/IQ/IOS` 为主
- 大量使用 AWG 和 sample averaging

ADP7118A 展示了模拟动态器件演进：
- 多个 FOVI 同时参与
- `EN / VIN / VOUT` 协同扫描
- `TRIG_RESULT` 用于动态边界点
- 更像“资源 orchestration”而不是单项测量

代码生成/审查时可复用的判断框架：
- 这是数字模板型程序，还是模拟多源协同型程序？
- 资源绑定是否先于测量逻辑？
- 是否有清晰的初始化 / 收尾？
- 是否把静态测量、动态扫描、时序测量混淆了？

工程建议：
- 新器件开发时，优先从最接近的案例派生，而不是从空白模板硬写
- 数字器件优先找同逻辑家族案例
- 模拟器件优先找同类参数行为案例（reference / LDO / ADC / 运放）

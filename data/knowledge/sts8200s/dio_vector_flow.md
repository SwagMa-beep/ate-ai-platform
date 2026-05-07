# DIO_PLUS vector flow and fail capture

适用场景：
- 数字器件连通性 CON
- 功能测试 FUN
- 向量时序驱动与比较
- I2C 类串行数字交互

板卡能力：
- 8 路数字输入输出，电压范围 -2V 到 7V
- 速率：5MHz（DIO2.0_PLUS），16.6667MHz（DIO3.0）
- 板载向量存储器：1M / 8M per channel
- Per-pin T1/T2/T3 时序设置
- 支持 NRZ / RTZ / RTO / SBC 波形格式
- 支持错误捕捉与 fail map
- 可与 FOVI100、FPVI10、QVM 同步

软件使用要点：
- 首次使用（向量或 I2C）都应先调用 `Init()`
- 向量类测试通常先 `LoadVectorFile(...)`
- 再用 `Run(...)` 指定 label 区间执行
- 超时参数：
  - 默认等待 60 秒
  - `-1` 表示一直等待到结束
  - `-2` 表示不等待，适合异步轮询

典型向量流程：
1. `Init()`
2. `LoadVectorFile("xxx.vecdio")`
3. `Run("label_0", "label_1", timeout)`
4. `IsStop()` / `IsStoped()` 轮询完成状态
5. 检查 `IsHasFailLine()`
6. 必要时 `SaveFailMap()`
7. 读串行结果或 fail 行信息：
   - `GetSerialPatternResult(...)`
   - `GetFailLineInfos(...)`
   - `GetChannelFail(...)`
   - `GetChannelFailCount(...)`

Fail map 诊断建议：
- `SaveFailMap()` 最多保存 64K 失效行
- 对 FUN 测试，fail map 是最直接的定位工具
- 如果返回有失败，优先看失败行是不是集中在某个 label 或某个 pin

I2C 支持要点：
- 使用 `DIO_PLUS_I2CSITE_DEF_REG(...)` 在全局定义 I2C 工位
- 同一 I2C site 注册的物理通道不能重复
- `I2CInit(dataMaxByteCount)` 需要在 `Init()` 之后调用
- 如果不调用 `I2CInit`，系统默认按 256 字节预留向量空间

工程建议：
- CON/FUN 测试时，把向量 label 划分清楚，便于 `Run(startLabel, stopLabel)` 精准执行
- 若是调试阶段，先用较小 label 区间跑通，再扩到完整 vector
- 异步 `Run(..., -2)` 后必须配合 `IsStop()`，否则容易在向量未结束时读取结果
- 对串行协议，优先用 `GetSerialPatternResult()` 读关键信息，再结合 fail line 看细节

常见风险：
- 没有 `Init()` 就直接 `Run()`，尤其首次使用或切换模式后容易异常
- label 拼写或顺序错误，startLabel 在 stopLabel 后
- 只看 pass/fail，不保存 fail map，后续很难定位失效位置
- I2C site 在函数内部定义，导致配置不生效

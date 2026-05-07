# Digital form programming patterns

适用场景：
- 24PIN 数字通用适配器
- 无代码/低代码数字芯片测试程序
- 直流参数 + 功能测试快速搭建

模板结构理解：
- 固定基础文件：
  - `Template.ilk`
  - `Template.pdb`
  - `Template.pgs`
  - `Template.dll`
- 用户侧还需要：
  - `xxxx.vecdio` 向量文件

核心配置块：
- `GlobalVariable`
- `FUNCTION`
- `INLEVEL`
- `SUPPLY`
- `FIMV_PMU`
- `FVMI_PMU`

GlobalVariable 关键点：
- `VECTOR_FILE`：必须与 `Template.pgs` 同目录，类型必须是 `.vecdio`
- `AllGroup`：必须按 datasheet 原始管脚顺序填写
- `INGroup / OutGroup`：按输入/输出属性分组
- `UserGroup1~4`：预留给自定义测试分组

FUNCTION 使用要点：
- 功能测试是很多后续参数测试的前提
- VCC 电压量程要“高于且尽量接近目标值”
- 例如 6V 供电，不应随意选很高量程，优先选 `10V` 档

PMU 直流参数模板理解：
- `FIMV_PMU`：恒流测压，适合 `VIK / VOH / VOL` 这类电压结果
- `FVMI_PMU`：恒压测流，适合 `IIH / IIL / IOS` 这类电流结果

数字器件开发流程建议：
1. 根据 datasheet 创建 `vecdio`
2. 在向量编辑器里按真实 pin 名建管脚
3. 设置 DIO 通道映射
4. 复制 `Template.pgs` 改成芯片名
5. 修改 `GlobalVariable`
6. 先完成 `CON` / 功能测试
7. 再补 PMU 直流参数

实用经验：
- 向量文件名通常用芯片型号命名
- pin 名不能以数字开头，可在前面加字母前缀
- `CON` 常用 `FIMV_PMU` 做开短路类恒流测压检查
- 常见连接性测试电流先从 ±100uA 起步

双电源器件注意：
- 默认模板常用 `VCC1`
- 若要改成 `VCC2`，需同步修改：
  - `VCC_VALUE2`
  - `VCC_VRANG2`
  - `VCC_IRANG2`
- 双电源芯片需要同时配置 VCC1 和 VCC2

工程风险：
- `AllGroup` 顺序与 datasheet pin 顺序不一致，会导致整个向量定义错位
- `.vecdio` 不在同目录，PGS 装载后会报向量文件失败
- PMU 类型选错：把应当 `FVMI` 的电流参数写成 `FIMV`
- 电源量程远高于目标值，精度和保护都变差

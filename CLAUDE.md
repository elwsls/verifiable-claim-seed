# verifiable-claim-seed — CLAUDE.md

Machine-checkable claim contract + zero-dependency gate + real samples.
核心命题：**可复现≠可验证** (reproducible≠verifiable) —— repro+frozen/snapshot 只证内部一致性；外部正确性由 anchor 承担。PASS 永远带着影子出厂：doubt 表面 + stage 方向相位。

## Agent-first entry
1. 先读 `ai-catalog.json`（机器可读清单，含全部概念与入口）→ 再读本文件 → `llms.txt` 补充。
2. 跑 `python3 verifiable_claim_seed/verify_claim.py self-test` 确认门禁自检全绿（当前 49 例），再动任何东西。

## Commands
```sh
python3 verifiable_claim_seed/verify_claim.py self-test    # gate 自检（49 cases，须全绿才动手）
python3 verifiable_claim_seed/verify_claim.py verify <claim.json> [--report out.json]
python3 verifiable_claim_seed/mcp_agent_sim.py            # 模拟陌生 agent 走 MCP 全链路（8 cases）
verify-claim self-test                                     # pip install verifiable-claim-seed 后
```
退出码：**0** 全过 / **1** 硬失败（结构/格式/声明引用的文件缺失） / **2** 用法·环境 / **3** 证据契约违规（哈希失配/复现不符/引用句不在快照）。

## Architecture（字段即契约，无散文歧义）
- `verifiable_claim_seed/schema/verifiable-claim-v1.schema.json` — 声明契约规格（JSON Schema 2020-12，additionalProperties:false，tier 规则在 allOf）。
- `verifiable_claim_seed/verify_claim.py` — **实际校验器**（纯 stdlib，不依赖 jsonschema）。schema 与 gate 是平行实现；`self-test` 的「schema-gate 契约同步」例机器核验两者不漂移（字段/枚举/required 列表/嵌套白名单）。
- 三份真实声明：`verifiable_claim_seed/claims/VC-20260815-001.json`（ISS 轨道高度，derived + frozen + repro）· `VC-20260823-001/002`（1 万步，primary + text-quote 锚 + 源快照）。
- MCP server：`verifiable_claim_seed/mcp_server.py`（stdio，零依赖；tools：self_test / validate / verify-with-allow_execution）。
- MCP 模拟 agent：`verifiable_claim_seed/mcp_agent_sim.py`——以 subprocess 走完整 MCP 链路，验证陌生 agent 发现→决策→调用零人工可用（8 cases）。

## 硬规则（每次改动）
1. **self-test 须先绿再改，改后必绿**：任何新行为必须加自检用例。
2. **schema-gate 同步守卫**：改 schema 的字段/枚举/required 必须镜像到 `verify_claim.py` 常量（`SCHEMA_FIELDS` / `*_FIELDS` / `*_REQUIRED` / `TEXT_QUOTE_REQUIRED`），否则自检的漂移守卫失败。
3. **每改必 commit**；删除用 `trash`，禁 `rm`。

## 设计边界（动手前必读，都是故意的）
- **无沙箱**：`verify` 以 subprocess 真实执行 `repro.script`（120s 超时）——只验证你信任的声明；验证来源不受信的声明等于在本机执行其任意代码。
- **路径语义**：声明内 `data/`/`scripts/` 路径相对包根解析，非相对声明 JSON。拷单文件声明到别处即断。
- **repro.script 必须为 Python**（sys.executable 执行）；shell/其他语言会被当失败脚本误报。
- **设计边界**：门禁验"脚本按其声明输出"，不验"脚本计算正确"——伪造脚本打印正确哈希+期望数值即可过 rc0。完整性来自冻结输入字节与声明自洽，非数学。
- **text-quote 锚带字节快照**：`quote + locator + snapshot + snapshot_sha256`；gate 核快照哈希 + 引用句须真实存在于快照文本（排版/空白归一化比对）。机器核的是"引用句在这份快照里"；**快照是否确为现实源头仍须人工/AI 核**。
- **PASS 带影子**：空 doubt 表面 = peak 峰值信号，无影子的 PASS 最该被盯。
- **零依赖承诺**：gate 只用 Python stdlib；引入依赖即破坏核心卖点。

## 仓库关系
本仓是独立发布的公开仓（GitHub + PyPI + MCP registry），可整仓克隆或 `pip install verifiable-claim-seed`。打磨轨迹与审计记录不在此仓——公开仓不拖带内部上下文。

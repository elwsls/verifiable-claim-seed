# verifiable-claim-seed

> Machine-checkable claim contract + zero-dependency gate + real sample.
> 可复现≠可验证: repro+frozen prove internal consistency; external correctness is carried by the anchor.
> Agent-first: read `ai-catalog.json` before this file for the machine-readable manifest.
>
> `mcp-name: io.github.elwsls/verifiable-claim-seed`

## install

```sh
pip install verifiable-claim-seed     # zero dependencies, Python stdlib only
verify-claim self-test                # prove the gate works in this environment
```
Or clone the repo and run the gate directly:
```sh
python3 verifiable_claim_seed/verify_claim.py self-test
```

## entrypoints
| role | path |
|---|---|
| contract | `verifiable_claim_seed/schema/verifiable-claim-v1.schema.json` |
| gate | `verifiable_claim_seed/verify_claim.py` |
| real sample·航天 | `verifiable_claim_seed/claims/VC-20260815-001.json`（ISS 轨道高度，derived+frozen+repro） |
| real sample·健康 | `verifiable_claim_seed/claims/VC-20260823-001.json`（1 万步起源，text-quote 锚）· `verifiable_claim_seed/claims/VC-20260823-002.json`（步数-死亡趋平，text-quote 锚） |
| frozen data | `verifiable_claim_seed/data/iss_20260814.tle` |
| source snapshots | `verifiable_claim_seed/data/wcrf-10000-steps-20260823.html`（001 源快照）· `verifiable_claim_seed/data/pmc-9289978-20260823.html`（002 源快照） |
| repro script | `verifiable_claim_seed/scripts/verify_iss.py` |
| MCP server | `verifiable_claim_seed/mcp_server.py`（stdio，命令 `verifiable-claim-mcp` / `verifiable-claim-seed`） |
| MCP agent sim | `verifiable_claim_seed/mcp_agent_sim.py`（模拟陌生 agent 走完整 MCP 链路，零人工可用验证） |
| MCP registry manifest | `server.json`（`io.github.elwsls/verifiable-claim-seed`，PyPI/stdio） |
| exhibit·概念 | `docs/news-appendix.md`（人类样张，**非机器声明**——verify_tier 独立于 schema tier，不参与门禁） |
| exhibit·新闻稿 | `docs/news-release-10000-steps.md`（人类样张·新闻稿，**非机器声明**，对应 VC-20260823-001/002） |
| exhibit·学术声明 | `docs/academic-claim-10000-steps.md`（人类样张·学术声明，**非机器声明**，对应 VC-20260823-001/002） |

## verify
```sh
verify-claim self-test                              # pip 安装后
verify-claim verify <claim.json> [--report out.json]
# 仓库内直接跑：
python3 verifiable_claim_seed/verify_claim.py self-test
```
退出码：**0** 全过 / **1** 硬失败（结构/格式/声明引用的文件缺失） / **2** 用法·环境（命令行实参/待验证声明文件缺失） / **3** 证据契约违规（哈希失配/复现不符）。

> **路径语义**：声明内 `data/`/`scripts/` 路径相对**包根（gate 脚本所在目录）**解析，非相对声明 JSON。验证外部拷来的单文件声明前请保持完整仓库结构，或把整个声明放回 `verifiable_claim_seed/claims/`。
> **text-quote 锚带字节快照**：`anchor.mode=text-quote` 必须带 `quote + locator + snapshot + snapshot_sha256`（source snapshot 文件路径 + 64 位哈希）。gate 逐字节核验快照哈希，并抽取快照文本做「排版字符归一化 + 去空白」的紧凑比对——**逐字引用句须真实存在于冻结快照**（HTML 实体/渲染空格不会误报）。机器核的是"引用句在这份快照里"；快照是否确为现实源头仍须人工/AI 核。
> **repro.script 为 Python**：`repro.script` 由 `python3` 执行（subprocess，120s 超时）——脚本必须是 Python。**无沙箱**：门禁不隔离，路径可穿越包根，且以调用者权限运行；安全完全依赖"只验证你信任的声明"。
> 零依赖说明：`verify_claim.py` 是**实际校验器**（纯 stdlib，不依赖 jsonschema 库）；`schema/*.json` 是契约规格——两者由 self-test 的「schema-gate 契约同步」例机器核验不漂移。anchor.sha256 同样被钉死：指向仓库内文件即逐字节核验（失配 rc3）。
> 安全注意：`verify` 会**真实执行声明中的 `repro.script`**。只验证你信任的声明；验证来源不受信的声明等于在本机执行其声明的任意代码。
> **设计边界**：门禁验"脚本按其声明输出"，不验"脚本计算正确"——伪造 `repro.script` 打印正确哈希 + 期望数值即可通过 rc0。完整性来自**冻结输入字节**（anchor/frozen）与声明自洽，非数学。"只验证你信任的声明"因此是安全前提，不是装饰。

## MCP server
`verifiable-claim-mcp`（或 registry 启动别名 `verifiable-claim-seed`）暴露三工具（stdio，零依赖）：
- `self_test` — gate 自检，PASS/FAIL + case 数
- `validate` — 结构 + 哈希检查，**不执行脚本**（对不受信声明用这个）
- `verify` — 完整校验，**须显式 `allow_execution=true`**（会执行声明内 repro.script，即任意代码）；无该标志一律拒绝

MCP registry：`server.json`（`io.github.elwsls/verifiable-claim-seed`，PyPI/stdio）。

Claude Code 接线（`pip install` 后）——项目根放 `.mcp.json`（仓内已带示例），新会话自动加载三工具：
```json
{ "mcpServers": { "verifiable-claim-seed": { "command": "python3", "args": ["verifiable_claim_seed/mcp_server.py"] } } }
```
也可用 `uvx verifiable-claim-seed`（PyPI 发布后）。陌生 agent 端到端已验证：发现三工具 → validate 零执行 → verify 缺 `allow_execution` 拒 → 带标志过。

License: MIT. Zero dependencies (Python stdlib).

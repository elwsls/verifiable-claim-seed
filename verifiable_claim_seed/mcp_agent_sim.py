#!/usr/bin/env python3
"""mcp_agent_sim.py — 模拟陌生 agent 通过 stdio 与 verifiable-claim-mcp 对话。

验证「零人工自主可用」的 MCP 链路：agent 发现工具 → 读描述做决策 → 正确调用。
与真实 MCP client 走完全相同的 NDJSON JSON-RPC 2.0 over stdio。

决策路径（agent 视角）：
  1. initialize              → 握手
  2. tools/list              → 发现 self_test / validate / verify
  3. 读描述做决策：
     - 不受信声明 → validate（零执行）          → 断言 valid + isError=false
     - 信任声明 verify 缺 allow_execution        → 断言 refused rc2 + isError=true
     - 信任声明 verify + allow_execution=true    → 断言 rc0 + isError=false
  4. self_test               → 断言 passed

用法：
  python3 verifiable_claim_seed/mcp_agent_sim.py                          # 仓内 server
  python3 verifiable_claim_seed/mcp_agent_sim.py --command verifiable-claim-mcp   # wheel 装的 console script

退出码：0 全过 / 1 失败
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(HERE, "mcp_server.py")
CLAIM = os.path.join(HERE, "claims", "VC-20260815-001.json")


def _send(proc, msg):
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("server 无响应（可能启动失败）")
    return json.loads(line)


def main(argv=None):
    cmd = ["python3", SERVER]
    if argv and argv[0] == "--command":
        cmd = [argv[1]]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8")
    counter = [0]

    def call(method, params=None):
        counter[0] += 1
        msg = {"jsonrpc": "2.0", "method": method, "id": counter[0]}
        if params is not None:
            msg["params"] = params
        return _send(proc, msg)

    results = []

    def case(name, cond, detail=""):
        results.append((name, cond))
        print("  %s  %s%s" % ("PASS" if cond else "FAIL", name,
                              (" — " + detail if detail else "")))

    # 1. initialize
    r = call("initialize", {})
    info = r["result"]["serverInfo"]
    case("initialize 握手", info["name"] == "verifiable-claim-seed",
         "name=%s v=%s" % (info["name"], info["version"]))

    # 2. tools/list：发现三工具 + 描述语义
    r = call("tools/list")
    tools = {t["name"]: t for t in r["result"]["tools"]}
    case("tools/list 暴露三工具", sorted(tools) == ["self_test", "validate", "verify"],
         ",".join(sorted(tools)))
    case("validate 描述明示零执行",
         "WITHOUT executing" in tools["validate"]["description"]
         or "不执行" in tools["validate"]["description"])
    case("verify 描述明示 allow_execution",
         "allow_execution" in tools["verify"]["description"]
         and "REQUIRES allow_execution" in tools["verify"]["description"])

    # 3a. 不受信声明 → validate（零执行，agent 的安全选择）
    r = call("tools/call", {"name": "validate", "arguments": {"claim_path": CLAIM}})
    txt = json.loads(r["result"]["content"][0]["text"])
    case("不受信声明 → validate 零执行",
         txt.get("valid") is True and r["result"]["isError"] is False,
         "valid=%s" % txt.get("valid"))

    # 3b. 信任声明 verify 缺 allow_execution → 拒
    r = call("tools/call", {"name": "verify", "arguments": {"claim_path": CLAIM}})
    txt = json.loads(r["result"]["content"][0]["text"])
    case("verify 缺 allow_execution 拒 rc2",
         txt.get("refused") is True and txt.get("exit_code") == 2
         and r["result"]["isError"] is True,
         "exit_code=%s" % txt.get("exit_code"))

    # 3c. 信任声明 verify + allow_execution=true → rc0
    r = call("tools/call", {"name": "verify",
                            "arguments": {"claim_path": CLAIM,
                                          "allow_execution": True}})
    txt = json.loads(r["result"]["content"][0]["text"])
    case("verify + allow_execution=true rc0",
         txt.get("exit_code") == 0 and r["result"]["isError"] is False,
         "exit_code=%s" % txt.get("exit_code"))

    # 4. self_test
    r = call("tools/call", {"name": "self_test", "arguments": {}})
    txt = json.loads(r["result"]["content"][0]["text"])
    tail = txt.get("output", "").strip().splitlines()[-1] if txt.get("output") else ""
    case("self_test passed", txt.get("passed") is True, tail)

    proc.stdin.close()
    proc.wait()

    ok = all(c for _, c in results)
    if ok:
        print("MCP AGENT SIM OK（%d cases）" % len(results))
        return 0
    print("MCP AGENT SIM FAILED（%d/%d cases）"
          % (sum(1 for _, c in results if c), len(results)))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""verifiable-claim-mcp — zero-dependency MCP server over stdio (JSON-RPC 2.0).

NDJSON over stdio，纯 Python stdlib。暴露三工具：
- self_test: gate 自检，PASS/FAIL + case 数
- validate: 结构 + 锚/冻结哈希检查，不执行任何代码
- verify: 完整校验（会执行声明内 repro.script，即任意代码），须显式 allow_execution=true

安全：verify 以调用者权限执行声明内任意 Python 代码（无沙箱）。
只对"你信任的声明"调用 verify；validate 是零执行的安全路径。

用法：
  verifiable-claim-mcp          # 读 stdin NDJSON 请求，写 stdout 响应
"""
import io
import json
import os
import sys
import tempfile

try:
    from .verify_claim import BASE, check_content, check_structure, cmd_self_test, verify_claim
except ImportError:
    from verify_claim import BASE, check_content, check_structure, cmd_self_test, verify_claim

SERVER_NAME = "verifiable-claim-seed"
VERSION = "1.3.0"

TOOLS = [
    {
        "name": "self_test",
        "description": "Run the gate self-test: proves the tool works in this environment. Returns passed/exit_code/output.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "validate",
        "description": "Check a claim's structure and anchor/frozen hashes WITHOUT executing any code. Safe for untrusted claims. Args: claim (claim JSON text) or claim_path (absolute file path).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "claim": {"type": "string", "description": "Claim document as JSON text"},
                "claim_path": {"type": "string", "description": "Absolute path to a claim JSON file"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "verify",
        "description": "Full verification of a claim, INCLUDING executing its repro.script as arbitrary code with no sandbox. REQUIRES allow_execution=true; otherwise refused. Only call this on claims you trust. Args: claim or claim_path, allow_execution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "claim": {"type": "string", "description": "Claim document as JSON text"},
                "claim_path": {"type": "string", "description": "Absolute path to a claim JSON file"},
                "allow_execution": {"type": "boolean",
                                    "description": "Must be true; verify is refused without it"},
            },
            "required": ["allow_execution"],
            "additionalProperties": False,
        },
    },
]


def _resolve_claim(args):
    """从 arguments 解析出 claim 文件路径。返回 (path, error)；claim 文本会写临时文件。"""
    claim_text = args.get("claim")
    claim_path = args.get("claim_path")
    if claim_text and claim_path:
        return None, "claim 与 claim_path 只能给一个"
    if claim_text:
        if not isinstance(claim_text, str):
            return None, "claim 必须为字符串（JSON 文本）"
        fd, tmp = tempfile.mkstemp(suffix=".json", prefix="vcs-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(claim_text)
        except Exception as e:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            return None, "claim 文本写入临时文件失败: %s" % e
        return tmp, None
    if claim_path:
        if not os.path.isfile(claim_path):
            return None, "claim_path 不存在: %s" % claim_path
        return claim_path, None
    return None, "须提供 claim（JSON 文本）或 claim_path（文件路径）"


def _capture(fn, *args, **kwargs):
    """执行 fn 并捕获其 stdout（MCP 的 stdout 是传输通道，不能污染）。返回 (fn 返回值, 捕获文本)。"""
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        ret = fn(*args, **kwargs)
    finally:
        sys.stdout = old
    return ret, buf.getvalue()


def handle_self_test(params):
    rc, out = _capture(cmd_self_test, [])
    return {"passed": rc == 0, "exit_code": rc, "output": out.strip()}


def _validate_claim(path):
    try:
        c = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        return {"valid": False, "exit_code": 1, "structure": False,
                "errors": ["JSON 解析失败: %s" % e]}
    structure_errors = []
    check_structure(c, structure_errors,
                    claims_dir=os.path.dirname(os.path.abspath(path)))
    content_errors = []
    if not structure_errors:
        rc, _ = check_content(c, BASE, content_errors, run_repro=False)
    else:
        rc = 1
    errors = structure_errors + content_errors
    return {"valid": rc == 0 and not errors,
            "exit_code": rc if (rc or errors) else 0,
            "structure": not structure_errors,
            "errors": errors}


def handle_validate(args):
    path, err = _resolve_claim(args)
    if err:
        return {"valid": False, "error": err}
    try:
        return _validate_claim(path)
    finally:
        if args.get("claim"):
            try:
                os.unlink(path)
            except OSError:
                pass


def handle_verify(args):
    if args.get("allow_execution") is not True:
        return {"refused": True, "exit_code": 2,
                "error": "verify 会执行声明内 repro.script（任意代码，无沙箱）；"
                         "须显式传 allow_execution=true。对不受信声明请用 validate（零执行）。"}
    path, err = _resolve_claim(args)
    if err:
        return {"exit_code": 2, "error": err}
    try:
        (rc, report), _ = _capture(verify_claim, path, BASE)
        report["exit_code"] = rc
        return report
    finally:
        if args.get("claim"):
            try:
                os.unlink(path)
            except OSError:
                pass


def _send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _tool_is_error(name, result):
    if name == "self_test":
        return not result.get("passed", False)
    if name == "validate":
        return not result.get("valid", False) or "error" in result
    if name == "verify":
        return result.get("exit_code", 0) != 0
    return False


def _handle_call(msg):
    params = msg.get("params", {}) or {}
    name = params.get("name")
    args = params.get("arguments", {}) or {}
    if not isinstance(args, dict):
        args = {}
    try:
        if name == "self_test":
            result = handle_self_test(args)
        elif name == "validate":
            result = handle_validate(args)
        elif name == "verify":
            result = handle_verify(args)
        else:
            _send({"jsonrpc": "2.0", "id": msg["id"],
                   "error": {"code": -32602, "message": "unknown tool: %s" % name}})
            return
        _send({"jsonrpc": "2.0", "id": msg["id"],
               "result": {
                   "content": [{"type": "text",
                                "text": json.dumps(result, ensure_ascii=False, indent=2)}],
                   "isError": _tool_is_error(name, result),
               }})
    except Exception as e:
        _send({"jsonrpc": "2.0", "id": msg["id"],
               "error": {"code": -32603, "message": "internal error: %s" % e}})


def main(argv=None):
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        method = msg.get("method")
        has_id = "id" in msg
        if method == "initialize" and has_id:
            _send({"jsonrpc": "2.0", "id": msg["id"], "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": VERSION},
            }})
        elif method == "notifications/initialized":
            continue
        elif method == "ping" and has_id:
            _send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
        elif method == "tools/list" and has_id:
            _send({"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": TOOLS}})
        elif method == "tools/call" and has_id:
            _handle_call(msg)
        elif has_id:
            _send({"jsonrpc": "2.0", "id": msg["id"],
                   "error": {"code": -32601, "message": "method not found: %s" % method}})
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""verify_claim.py — 可验证声明门禁（零依赖 stdlib，Python 3.6+）。

纪律模式：self-test 自检 / 格式契约 / 退出码 / --report。
可复现≠可验证：structure 检查证明声明结构合法（可被机器解析）；
content 检查证明 frozen/快照哈希与 repro 复现真实（可复现），并证明
text-quote 的逐字引用句真实存在于冻结源快照文本；外部正确性由 anchor
承担（快照哈希只能证明"引用句在这份快照里"，证明不了快照确为现实源头——
源头真假与声明的解释须人工/AI 核）。

用法：
  python3 verify_claim.py self-test                          # 自检（PASS/FAIL, 0/1）
  python3 verify_claim.py verify <claim.json> [--report out.json]

退出码：0 全过 / 1 硬失败（结构/格式/引用文件缺失） / 2 用法·环境 / 3 证据契约违规（哈希失配/复现不符）

引用文件路径相对本脚本所在目录（BASE）解析，与运行目录无关。
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser

FORMAT = "verifiable-claim-v1"
CLAIM_ID = re.compile(r"^VC-\d{8}-\d{3,}$")
SHA64 = re.compile(r"^[a-f0-9]{64}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_valid_date(s):
    """历法校验：YYYY-MM-DD 且为真实存在的日期（schema format:date 的语义，非仅形状）。

    用 datetime.strptime 校验闰年与月末，2 月允许 29（闰年由 strptime 判定）。
    """
    if not isinstance(s, str) or not DATE_RE.match(s):
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False
TOP_REQUIRED = ("format", "claim_id", "statement", "made_at", "tier")
ANCHOR_REQUIRED = ("mode", "source", "asof")
REPRO_REQUIRED = ("script",)
FROZEN_REQUIRED = ("file", "sha256")
DOUBT_REQUIRED = ("kind", "what", "since", "stage")
SCHEMA_FIELDS = ("format", "claim_id", "statement", "made_at", "tier",
                 "assumptions", "anchor", "repro", "frozen", "supersedes",
                 "stage", "doubt")
TIERS = ("primary", "derived", "computed")
STAGES = ("growing", "settled", "peak", "trough")
DOUBT_KINDS = ("unverified", "suspect", "limitation")
# 嵌套对象字段白名单（与 schema 的 additionalProperties:false 对齐，check_schema_sync 校验不漂移）
ANCHOR_FIELDS = ("mode", "source", "asof", "quote", "locator", "file", "sha256",
                 "snapshot", "snapshot_sha256")
TEXT_QUOTE_REQUIRED = ("quote", "locator", "snapshot", "snapshot_sha256")
REPRO_FIELDS = ("script", "args", "expect_exit", "expect_sha256", "expect_values")
FROZEN_FIELDS = ("file", "sha256")
DOUBT_FIELDS = ("kind", "what", "since", "stage")
BASE = os.path.dirname(os.path.abspath(__file__))


def truncate(sha):
    return sha[:8] + "…" + sha[-4:]


class _TextExtractor(HTMLParser):
    """从 HTML/XML 快照中抽取可见文本（stdlib，零依赖）。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def extract_html_text(raw):
    p = _TextExtractor()
    p.feed(raw.decode("utf-8", errors="replace"))
    return "".join(p.parts)


def normalize_quote_text(s):
    """逐字引用句的机器比对归一化：排版字符→ASCII + 去全部空白。

    HTML 渲染常把同一文本呈现成不同空白形态（WCRF 页实测：引号后逗号前
    多一个渲染空格、"Manpo-kei" 用弯引号）。为免纯空白/排版伪差误报，
    比对时智能引号/破折号归一到 ASCII、去全部空白，再做紧凑子串匹配。
    """
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
                 ("–", "-"), ("—", "-"), ("―", "-"),
                 (" ", " "), (" ", " "), (" ", " "), ("​", "")):
        s = s.replace(a, b)
    return re.sub(r"\s+", "", s)


def check_structure(c, errors, claims_dir=None):
    """结构检查：声明是否合法、可被机器解析。硬失败 rc1。

    claims_dir：声明所在目录，用于校验 supersedes 指向的 claim 文件存在性
    （谱系链"X 取代 Y"必须能机器核到 Y 在场，否则可宣称取代任何不存在的东西）。
    """
    if c.get("format") != FORMAT:
        errors.append("format 必须为 %s，实际 %r" % (FORMAT, c.get("format")))
    for f in TOP_REQUIRED:
        if f not in c:
            errors.append("缺必填字段 %s" % f)
    for k in c:
        if k not in SCHEMA_FIELDS:
            errors.append("未知顶层字段 %s（additionalProperties:false）" % k)

    cid = c.get("claim_id")
    if cid is not None and not CLAIM_ID.match(cid):
        errors.append("claim_id 须为 VC-YYYYMMDD-NNN: %r" % cid)

    made = c.get("made_at")
    if made is not None and not is_valid_date(made):
        errors.append("made_at 须为真实日期 YYYY-MM-DD: %r" % made)

    tier = c.get("tier")
    if tier is not None and tier not in TIERS:
        errors.append("tier 非法: %r" % tier)
    if tier == "primary" and "anchor" not in c:
        errors.append("tier=primary 必须有 anchor")
    if tier in ("derived", "computed"):
        for f in ("anchor", "frozen", "repro"):
            if f not in c:
                errors.append("tier=%s 必须有 %s（可复现≠可验证）" % (tier, f))
    if tier == "computed" and "assumptions" not in c:
        errors.append("tier=computed 必须显式声明 assumptions")

    a = c.get("anchor")
    if isinstance(a, dict):
        for f in ANCHOR_REQUIRED:
            if f not in a:
                errors.append("anchor 缺 %s" % f)
        mode = a.get("mode")
        if mode not in ("frozen-bytes", "text-quote"):
            errors.append("anchor.mode 非法: %r" % mode)
        if a.get("asof") is not None and not is_valid_date(a["asof"]):
            errors.append("anchor.asof 须为真实日期 YYYY-MM-DD: %r" % a.get("asof"))
        for k in a:
            if k not in ANCHOR_FIELDS:
                errors.append("anchor 未知字段 %s（additionalProperties:false）" % k)
        if mode == "text-quote":
            for f in TEXT_QUOTE_REQUIRED:
                if not a.get(f):
                    errors.append("anchor.mode=text-quote 必须带 %s（逐字引用句+定位+源快照字节承诺）"
                                  % f)
            if a.get("snapshot_sha256") and not SHA64.match(a["snapshot_sha256"]):
                errors.append("anchor.snapshot_sha256 须为 64 位 hex")
        else:
            for f in ("file", "sha256"):
                if not a.get(f):
                    errors.append("anchor.mode=frozen-bytes 必须带 %s" % f)
            if a.get("sha256") and not SHA64.match(a["sha256"]):
                errors.append("anchor.sha256 须为 64 位 hex")
    elif "anchor" in c:
        errors.append("anchor 必须为对象")

    fr = c.get("frozen")
    if isinstance(fr, dict):
        if not fr.get("file"):
            errors.append("frozen 缺 file")
        if not fr.get("sha256") or not SHA64.match(fr.get("sha256", "")):
            errors.append("frozen.sha256 须为 64 位 hex")
        for k in fr:
            if k not in FROZEN_FIELDS:
                errors.append("frozen 未知字段 %s（additionalProperties:false）" % k)
    elif "frozen" in c:
        errors.append("frozen 必须为对象")

    rp = c.get("repro")
    if isinstance(rp, dict):
        for f in REPRO_REQUIRED:
            if not rp.get(f):
                errors.append("repro 缺 %s" % f)
        ee = rp.get("expect_exit")
        if ee is not None and (isinstance(ee, bool) or not isinstance(ee, int)):
            errors.append("repro.expect_exit 必须为整数（bool 不算）")
        if rp.get("expect_sha256") and not SHA64.match(rp["expect_sha256"]):
            errors.append("repro.expect_sha256 须为 64 位 hex")
        ev = rp.get("expect_values")
        if ev is not None:
            if not isinstance(ev, dict):
                errors.append("repro.expect_values 必须为对象（label→期望值字符串）")
            else:
                for k, v in ev.items():
                    if not isinstance(k, str) or not k or not isinstance(v, str) or not v:
                        errors.append("repro.expect_values 项须为 label→值字符串: %r" % (k, v))
        for k in rp:
            if k not in REPRO_FIELDS:
                errors.append("repro 未知字段 %s（additionalProperties:false）" % k)
    elif "repro" in c:
        errors.append("repro 必须为对象")

    ss = c.get("supersedes")
    if ss is not None:
        if not isinstance(ss, list):
            errors.append("supersedes 必须为数组")
        else:
            for s in ss:
                if not CLAIM_ID.match(s):
                    errors.append("supersedes 项须为 claim_id: %r" % s)
                elif claims_dir is not None and not os.path.exists(
                        os.path.join(claims_dir, s + ".json")):
                    errors.append("supersedes 指向不存在的 claim 文件: %r（谱系链须能核到被取代者在场）"
                                  % s)

    stage = c.get("stage")
    if stage is not None and stage not in STAGES:
        errors.append("stage 非法: %r（须为 %s）" % (stage, "/".join(STAGES)))

    dt = c.get("doubt")
    if dt is not None:
        if not isinstance(dt, list):
            errors.append("doubt 必须为数组")
        else:
            for i, item in enumerate(dt):
                if not isinstance(item, dict):
                    errors.append("doubt[%d] 必须为对象" % i)
                    continue
                for f in DOUBT_FIELDS:
                    if f not in item:
                        errors.append("doubt[%d] 缺 %s" % (i, f))
                if item.get("kind") not in DOUBT_KINDS:
                    errors.append("doubt[%d].kind 非法: %r（须为 %s）"
                                  % (i, item.get("kind"), "/".join(DOUBT_KINDS)))
                if "what" in item and not item.get("what"):
                    errors.append("doubt[%d].what 为空" % i)
                if item.get("stage") not in STAGES:
                    errors.append("doubt[%d].stage 非法: %r（须为 %s）"
                                  % (i, item.get("stage"), "/".join(STAGES)))
                if "since" in item and not is_valid_date(item["since"]):
                    errors.append("doubt[%d].since 须为真实日期 YYYY-MM-DD: %r" % (i, item.get("since")))
                for k in item:
                    if k not in DOUBT_FIELDS:
                        errors.append("doubt[%d] 未知字段 %s（additionalProperties:false）" % (i, k))


def check_content(c, base, errors, run_repro=True):
    """内容契约：冻结文件哈希 + 复现跑通。返回 rc 增量（1 引用缺失 / 3 契约不符）。

    run_repro=False 跳过 repro 脚本执行（只做结构已验的锚/冻结哈希检查）——
    MCP validate 工具用它实现"不执行代码"的安全校验路径。tier 结构要求（derived
    必须声明 repro）由 check_structure 强制，与是否执行无关。
    """

    rc = 0
    evidence = []
    a = c.get("anchor")
    if (isinstance(a, dict) and a.get("mode") == "frozen-bytes"
            and a.get("file") and a.get("sha256")):
        apath = os.path.join(base, a["file"])
        if os.path.exists(apath):
            actual = hashlib.sha256(open(apath, "rb").read()).hexdigest()
            if actual != a["sha256"]:
                errors.append("anchor.sha256 失配 %s: 实际 %s"
                              % (a["file"], truncate(actual)))
                rc = max(rc, 3)
            else:
                evidence.append("anchor 冻结字节哈希已核验: %s" % a["file"])
        else:
            # frozen-bytes 锚承诺"字节可核"却无字节可核：与 text-quote 的"外部源由人核"不同，
            # 无法区分笔误路径与"故意外部锚"——宁可判证据契约违规也不静默放行。
            errors.append("anchor 文件缺失: %s（frozen-bytes 锚必须可核验字节）" % a["file"])
            rc = max(rc, 3)
    if (isinstance(a, dict) and a.get("mode") == "text-quote"
            and a.get("snapshot") and a.get("snapshot_sha256")):
        # text-quote 锚钉字节快照：逐字引用句须真实存在于冻结快照文本，
        # 否则 quote 真假只有"人说了算"——与 frozen-bytes 同强度后机器可核。
        spath = os.path.join(base, a["snapshot"])
        if not os.path.exists(spath):
            errors.append("anchor 快照文件缺失: %s（text-quote 锚须可核验字节）" % a["snapshot"])
            rc = max(rc, 3)
        else:
            raw = open(spath, "rb").read()
            actual = hashlib.sha256(raw).hexdigest()
            if actual != a["snapshot_sha256"]:
                errors.append("anchor.snapshot_sha256 失配 %s: 实际 %s"
                              % (a["snapshot"], truncate(actual)))
                rc = max(rc, 3)
            else:
                quote = a.get("quote") or ""
                if not normalize_quote_text(quote):
                    errors.append("anchor.quote 为空，无法锚定到快照文本")
                    rc = max(rc, 3)
                elif normalize_quote_text(quote) not in normalize_quote_text(
                        extract_html_text(raw)):
                    errors.append("anchor.quote 未在快照 %s 文本中出现（逐字引用句须真实在场）"
                                  % a["snapshot"])
                    rc = max(rc, 3)
                else:
                    evidence.append("text-quote 锚快照哈希已核验 + 引用句已锚定快照: %s"
                                    % a["snapshot"])
    fr = c.get("frozen")
    if isinstance(fr, dict):
        path = os.path.join(base, fr.get("file", ""))
        if not os.path.exists(path):
            errors.append("frozen 文件缺失: %s" % fr.get("file"))
            rc = max(rc, 1)
        else:
            actual = hashlib.sha256(open(path, "rb").read()).hexdigest()
            if actual != fr.get("sha256"):
                errors.append("frozen.sha256 失配 %s: 实际 %s" % (fr.get("file"), truncate(actual)))
                rc = max(rc, 3)
            else:
                evidence.append("frozen 冻结快照哈希已核验: %s" % fr.get("file"))

    rp = c.get("repro")
    if run_repro and isinstance(rp, dict) and rp.get("script"):
        script = os.path.join(base, rp["script"])
        if not os.path.exists(script):
            errors.append("repro 脚本缺失: %s" % rp["script"])
            rc = max(rc, 1)
        else:
            args = [rp["script"]] + list(rp.get("args", []))
            try:
                p = subprocess.run([sys.executable] + args, cwd=base,
                                   capture_output=True, text=True, timeout=120)
                out = p.stdout + p.stderr
                ee = rp.get("expect_exit")
                if ee is not None and p.returncode != ee:
                    errors.append("repro 退出码 %s != 期望 %s" % (p.returncode, ee))
                    rc = max(rc, 3)
                ex = rp.get("expect_sha256")
                if ex:
                    # 等值匹配而非子串：期望哈希必须是输出中的独立 64 位 hex token，
                    # 嵌在更长 hex 串里不算。
                    # lookaround 排除前/后仍是 hex 的情况（70 个 0 里的前 64 位不算独立 token）。
                    hashes = re.findall(r"(?<![a-f0-9])[a-f0-9]{64}(?![a-f0-9])", out)
                    if ex not in hashes:
                        got = hashes[0] if hashes else None
                        errors.append("repro 输出未含期望 sha256: 期望 %s 实际 %s"
                                      % (truncate(ex), truncate(got) if got else "无"))
                        rc = max(rc, 3)
                ev = rp.get("expect_values")
                if isinstance(ev, dict) and ev:
                    # 结构化 label=value 输出解析：脚本须打印形如 alt_km=418.3 的行。
                    # statement 的派生数值与 repro 输出可能脱钩——若只验 sha256/退出码，
                    # 伪造脚本打印正确哈希即可通过。现逐值比对，且要求每个值出现在
                    # statement（声明正文）中，数值与证据闭环。
                    pairs = dict(re.findall(
                        r"(?m)(?<![A-Za-z0-9_])([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(-?[0-9]+(?:\.[0-9]+)?)",
                        out))
                    statement = c.get("statement") or ""
                    for label, want in ev.items():
                        got = pairs.get(label)
                        if got is None:
                            errors.append("repro 输出未含期望数值 %s=…（脚本须打印 label=value 行）"
                                          % label)
                            rc = max(rc, 3)
                        elif got != want:
                            errors.append("repro 输出 %s=%s != 期望 %s" % (label, got, want))
                            rc = max(rc, 3)
                        # 值须以独立 token 出现在声明正文（statement），防"声明说 999.9 而脚本算 418.3"
                        # 尾随英文句号 "." 是句子标点应放行（"418.3." 是合法英文句尾）
                        if not re.search(r"(?<![0-9A-Za-z.])" + re.escape(want) + r"(?![0-9A-Za-z])",
                                         statement):
                            errors.append("repro.expect_values[%s]=%s 未在 statement 中以独立 token 出现"
                                          % (label, want))
                            rc = max(rc, 3)
                    if rc < 3:
                        evidence.append("repro 复现跑通 + expect_values 数值已锚定: "
                                        + ", ".join("%s=%s" % (k, v) for k, v in ev.items()))
            except Exception as e:
                errors.append("repro 运行异常: %s" % e)
                rc = max(rc, 3)
            if not any(e.startswith("repro") for e in errors):
                evidence.append("repro 复现脚本已跑通: %s" % rp["script"])

    if (isinstance(a, dict) and isinstance(fr, dict)
            and a.get("mode") == "frozen-bytes"
            and a.get("file") and a["file"] == fr.get("file")
            and a.get("sha256") and fr.get("sha256")
            and a["sha256"] != fr["sha256"]):
        errors.append("anchor.sha256 与 frozen.sha256 指向同一文件却不一致: %s"
                      % a["file"])
        rc = max(rc, 3)
    return rc, evidence


def verify_claim(path, base):
    """校验单个声明 JSON。返回退出码。"""
    try:
        c = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        # 早返回路径必须与正常路径同构（rc, report）——否则 cmd_verify 拆包崩溃。
        err = "JSON 解析失败: %s" % e
        report = {
            "format": "verifiable-claim-gate-v2",
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "claim": {"file": os.path.basename(path), "claim_id": None,
                      "tier": None, "stage": None},
            "doubt": {"doubt_count": 0, "unverified": 0, "suspect": 0,
                      "limitation": 0, "turning": 0},
            "turning_doubt": [],
            "turning_stage": False,
            "checks": {"structure": {"pass": False, "errors": [err]},
                       "content": {"pass": False,
                                   "errors": ["content 未执行：JSON 无法解析"]}},
            "exit_code": 1,
            "summary": "硬失败/结构非法",
        }
        print_report(report, [err])
        return 1, report

    structure_errors = []
    content_errors = []
    check_structure(c, structure_errors,
                    claims_dir=os.path.dirname(os.path.abspath(path)))
    rc = 1 if structure_errors else 0
    content_ran = not structure_errors
    evidence = []
    if content_ran:
        rc, evidence = check_content(c, base, content_errors)
    errors = structure_errors + content_errors

    doubt = c.get("doubt") if isinstance(c.get("doubt"), list) else []
    dsum = {"doubt_count": len(doubt), "unverified": 0,
            "suspect": 0, "limitation": 0}
    turning = []
    for item in doubt:
        if not isinstance(item, dict):
            continue
        k = item.get("kind")
        if k in dsum:
            dsum[k] += 1
        if item.get("stage") in ("peak", "trough"):
            turning.append(item)
    dsum["turning"] = len(turning)
    claim_stage = c.get("stage")
    turning_stage = claim_stage in ("peak", "trough")

    report = {
        "format": "verifiable-claim-gate-v1",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "claim": {"file": os.path.basename(path),
                  "claim_id": c.get("claim_id"), "tier": c.get("tier"),
                  "stage": claim_stage},
        "doubt": dsum,
        "turning_doubt": turning,
        "turning_stage": turning_stage,
        "checks": {"structure": {"pass": not structure_errors,
                                 "errors": structure_errors},
                   "content": {"pass": content_ran and not content_errors,
                               "errors": content_errors if content_ran
                                        else ["content 未执行：structure 未通过"]}},
        "content_evidence": evidence,
        "exit_code": rc,
        "summary": ("全部检查通过" if rc == 0 else
                    "证据契约违规" if rc == 3 else "硬失败/结构非法")
    }
    print_report(report, errors)
    return rc, report


def print_report(report, errors):
    print("=== verify_claim 质检报告 ===")
    print("声明: %s  claim_id=%s tier=%s" % (report["claim"]["file"],
          report["claim"]["claim_id"], report["claim"]["tier"]))
    if errors:
        for e in errors:
            print("  FAIL  - %s" % e)
    else:
        ev = report.get("content_evidence") or []
        if any(x.startswith("repro 复现跑通 + expect_values") for x in ev):
            note = "可复现已证（哈希 + 派生数值已锚定）；外部正确性由 anchor 承担，quote 须人工/AI 核"
        elif any(x.startswith("text-quote 锚快照") for x in ev):
            note = "可复现（快照哈希已核验 + 引用句已锚定快照）；快照是否确为现实源头须人工/AI 核"
        elif ev:
            note = "可复现（哈希已核验）；外部正确性由 anchor 承担，quote 须人工/AI 核"
        else:
            # text-quote 软锚声明没有 frozen/repro：机器没验任何内容，不能说"可复现"
            note = "structure 合法；text-quote 软锚——quote 真伪机器未核验，须人工/AI 核"
        print("  PASS  structure + content（%s）" % note)
        sh = report.get("doubt") or {}
        if sh.get("doubt_count"):
            print("  doubt 表面: %d 项（未验 %d / 存疑 %d / 局限 %d）· claim stage=%s"
                  % (sh["doubt_count"], sh["unverified"], sh["suspect"],
                     sh["limitation"], report["claim"].get("stage") or "未声明"))
            if sh.get("turning"):
                for m in report.get("turning_doubt", []):
                    print("  转折信号[%s]: %s" % (m.get("stage"), m.get("what", "")[:60]))
            if report.get("turning_stage"):
                cs = report["claim"].get("stage")
                print("  转折信号[claim:%s]: 声明自身相位——agent 读转折信号不读静态 PASS"
                      % cs)
        else:
            print("  doubt 表面: 空——无影子的 PASS 最该被盯（peak 峰值信号）")
    print("---")
    print("退出码 %d · %s" % (report["exit_code"], report["summary"]))


# ---------- self-test ----------

def check_schema_sync():
    """schema 与 gate 契约漂移守卫：schema 的 properties/enum 必须与 gate 常量一致。
    gate 是手写平行实现，不读 schema 文件——本守卫在 self-test 中机器核验两边不漂移。"""
    errors = []
    schema_path = os.path.join(BASE, "schema", "verifiable-claim-v1.schema.json")
    if not os.path.exists(schema_path):
        errors.append("schema 文件缺失: %s" % schema_path)
        return errors
    try:
        s = json.load(open(schema_path, encoding="utf-8"))
    except Exception as e:
        errors.append("schema 解析失败: %s" % e)
        return errors
    props = s.get("properties", {})
    missing = [f for f in SCHEMA_FIELDS if f not in props]
    if missing:
        errors.append("gate 字段未入 schema: %s" % missing)
    gate_only = sorted(k for k in props if k not in SCHEMA_FIELDS)
    if gate_only:
        errors.append("schema 多出 gate 未覆盖字段: %s" % gate_only)
    if "tier" in props and set(props["tier"].get("enum", [])) != set(TIERS):
        errors.append("tier 枚举漂移: schema=%s" % props["tier"].get("enum"))
    if "stage" in props and set(props["stage"].get("enum", [])) != set(STAGES):
        errors.append("stage 枚举漂移: schema=%s" % props["stage"].get("enum"))
    dk = (props.get("doubt", {}).get("items", {})
          .get("properties", {}).get("kind", {}).get("enum", []))
    if dk and set(dk) != set(DOUBT_KINDS):
        errors.append("doubt.kind 枚举漂移: schema=%s" % dk)
    # 嵌套对象字段白名单漂移守卫：schema 的 properties 必须与 gate 的 *_FIELDS 一致
    nested = {"anchor": ANCHOR_FIELDS, "repro": REPRO_FIELDS, "frozen": FROZEN_FIELDS}
    for obj, known in nested.items():
        op = props.get(obj, {}).get("properties", {})
        missing = [f for f in known if f not in op]
        if missing:
            errors.append("gate %s 字段未入 schema: %s" % (obj, missing))
        schema_only = sorted(k for k in op if k not in known)
        if schema_only:
            errors.append("schema %s 多出 gate 未覆盖字段: %s" % (obj, schema_only))
    di = props.get("doubt", {}).get("items", {}).get("properties", {})
    if di:
        missing = [f for f in DOUBT_FIELDS if f not in di]
        if missing:
            errors.append("gate doubt 字段未入 schema: %s" % missing)
        schema_only = sorted(k for k in di if k not in DOUBT_FIELDS)
        if schema_only:
            errors.append("schema doubt 多出 gate 未覆盖字段: %s" % schema_only)
    # required 列表漂移守卫：schema 声明的必填必须与 gate 的 *_REQUIRED 常量一致。
    # （字段级/枚举级守卫查不到 required 列表漂移——schema 说 repro.expect_exit 可选，
    #   gate 却可能硬拒缺失，必须单列。）
    required_map = [
        ("顶层", s.get("required", []), TOP_REQUIRED),
        ("anchor", props.get("anchor", {}).get("required", []), ANCHOR_REQUIRED),
        ("repro", props.get("repro", {}).get("required", []), REPRO_REQUIRED),
        ("frozen", props.get("frozen", {}).get("required", []), FROZEN_REQUIRED),
        ("doubt", props.get("doubt", {}).get("items", {}).get("required", []), DOUBT_REQUIRED),
    ]
    for label, sch, gate in required_map:
        if set(sch) != set(gate):
            errors.append("%s required 漂移: schema=%s gate=%s"
                          % (label, sorted(sch), sorted(gate)))
    # text-quote 条件必填守卫：schema allOf/then 声明 text-quote 必带 quote+locator+snapshot+
    # snapshot_sha256，gate 用 TEXT_QUOTE_REQUIRED 平行实现——须机器核两边不漂移
    tq = set(TEXT_QUOTE_REQUIRED)
    for cond in s.get("allOf", []):
        then = (cond.get("then", {}).get("properties", {})
                .get("anchor", {}).get("required", []))
        if then and set(then) != tq:
            errors.append("schema text-quote 条件 required 漂移: schema=%s gate=%s"
                          % (sorted(then), sorted(tq)))
    return errors


def cmd_self_test(argv):
    cases = []
    with tempfile.TemporaryDirectory() as d:
        # 干净数据 + 复现脚本
        data_path = os.path.join(d, "data.json")
        with open(data_path, "w") as f:
            f.write('{"n": 1}')
        data_sha = hashlib.sha256(open(data_path, "rb").read()).hexdigest()
        ok_script = ("#!/usr/bin/env python3\n"
                     "import hashlib, sys\n"
                     "raw = open(sys.argv[1], 'rb').read()\n"
                     "print('sha256: ' + hashlib.sha256(raw).hexdigest())\n")
        with open(os.path.join(d, "verify_syn.py"), "w") as f:
            f.write(ok_script)
        bad_script = ok_script + "sys.exit(3)\n"
        with open(os.path.join(d, "verify_bad.py"), "w") as f:
            f.write(bad_script)
        # 输出 70 个 0（超长 hex 串）——用于断言 expect_sha256 是等值匹配而非子串包含
        with open(os.path.join(d, "sha_long.py"), "w") as f:
            f.write('#!/usr/bin/env python3\nprint("0" * 70)\n')
        # 派生数值输出：alt_km 行 + 哈希行（供 expect_values 解析）
        val_ok = ("#!/usr/bin/env python3\n"
                  "import hashlib, sys\n"
                  "raw = open(sys.argv[1], 'rb').read()\n"
                  "print('alt_km=418.3')\n"
                  "print('sha256: ' + hashlib.sha256(raw).hexdigest())\n")
        with open(os.path.join(d, "verify_val_ok.py"), "w") as f:
            f.write(val_ok)
        # 派生数值对不上（脚本算 999.9 而声明写 418.3）——expect_values 应判 rc3
        with open(os.path.join(d, "verify_val_bad.py"), "w") as f:
            f.write(val_ok.replace("418.3", "999.9"))
        # 带执行痕迹的脚本：被执行会在 cwd（=d）写 REPRO_EXECUTED——用于证明
        # check_content(run_repro=False) 不执行脚本（MCP validate 的安全路径）
        trace_script = ("#!/usr/bin/env python3\n"
                        "import hashlib, sys\n"
                        "open('REPRO_EXECUTED', 'w').write('x')\n"
                        "print('sha256: ' + hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())\n")
        with open(os.path.join(d, "verify_trace.py"), "w") as f:
            f.write(trace_script)
        trace_marker = os.path.join(d, "REPRO_EXECUTED")
        # text-quote 锚快照：HTML 实体（&ldquo;）+ 渲染空格（"Manpo-kei" 与逗号间多一空格）
        # ——引用句须在实体解码+去空白后仍能锚定（WCRF 页实测形态）
        snap_html = ('<html><body><p>The 10,000 steps a day target seems to have come about '
                     'from a trade name pedometer sold in 1965 by Yamasa Clock in Japan. '
                     'The device was called &ldquo;Manpo-kei&rdquo; , which translates to '
                     '&ldquo;10,000 steps meter&rdquo;. This was a marketing tool for the '
                     'device and has seemed to have stuck across the world as the daily '
                     'step target. It&rsquo;s even included in daily activity targets by '
                     'popular smartwatches, such as Fitbit.</p></body></html>')
        snap_path = os.path.join(d, "snap.html")
        with open(snap_path, "w", encoding="utf-8") as f:
            f.write(snap_html)
        snap_sha = hashlib.sha256(open(snap_path, "rb").read()).hexdigest()
        snap_quote = ('The 10,000 steps a day target seems to have come about from a trade '
                      'name pedometer sold in 1965 by Yamasa Clock in Japan. The device was '
                      'called “Manpo-kei”, which translates to “10,000 steps '
                      'meter”. This was a marketing tool for the device and has seemed '
                      'to have stuck across the world as the daily step target.')

        def clean():
            return {
                "format": FORMAT,
                "claim_id": "VC-20260823-001",
                "statement": "合成声明",
                "made_at": "2026-08-23",
                "tier": "derived",
                "anchor": {"mode": "frozen-bytes", "source": "syn",
                           "asof": "2026-08-23", "file": "data.json", "sha256": data_sha},
                "frozen": {"file": "data.json", "sha256": data_sha},
                "repro": {"script": "verify_syn.py", "args": ["data.json"],
                          "expect_exit": 0, "expect_sha256": data_sha},
                "supersedes": [],
                "stage": "peak",
                "doubt": [
                    {"kind": "limitation", "what": "合成局限：数据是临时文件",
                     "since": "2026-08-23", "stage": "settled"},
                    {"kind": "suspect", "what": "合成存疑：精度未核",
                     "since": "2026-08-23", "stage": "trough"},
                ],
            }

        def clean_quote():
            return {
                "format": FORMAT,
                "claim_id": "VC-20260823-002",
                "statement": "合成 text-quote 声明",
                "made_at": "2026-08-23",
                "tier": "primary",
                "anchor": {"mode": "text-quote", "source": "syn",
                           "asof": "2026-08-23", "quote": snap_quote,
                           "locator": "https://example.com/",
                           "snapshot": "snap.html", "snapshot_sha256": snap_sha},
                "supersedes": [],
                "stage": "settled",
                "doubt": [],
            }

        def run(name, mutate, want):
            c = clean()
            mutate(c)
            p = os.path.join(d, name + ".json")
            json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            rc, _ = verify_claim(p, d)
            cases.append((name, rc == want, rc, want))

        def run_quote(name, mutate, want):
            c = clean_quote()
            mutate(c)
            p = os.path.join(d, name + ".json")
            json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            rc, _ = verify_claim(p, d)
            cases.append((name, rc == want, rc, want))

        run("clean 合法声明通过", lambda c: None, 0)
        run("format 错误被拦", lambda c: c.update(format="wrong"), 1)
        run("缺必填字段被拦", lambda c: c.pop("statement"), 1)
        run("tier=primary 缺 anchor 被拦", lambda c: (c.update(tier="primary"), c.pop("anchor")), 1)
        run("derived 缺 repro 被拦", lambda c: c.pop("repro"), 1)
        run("computed 缺 assumptions 被拦", lambda c: c.update(tier="computed"), 1)
        run("anchor text-quote 缺 quote 被拦",
            lambda c: (c["anchor"].update(mode="text-quote", locator="p.1"),
                       c["anchor"].pop("file"), c["anchor"].pop("sha256")), 1)
        run("anchor sha256 非 64 位被拦",
            lambda c: c["anchor"].update(sha256="short"), 1)
        run("frozen 文件缺失被拦",
            lambda c: c["frozen"].update(file="nope.json"), 1)
        run("frozen 哈希失配判 rc3",
            lambda c: c["frozen"].update(sha256="f" * 64), 3)
        run("repro 退出码失配判 rc3",
            lambda c: c["repro"].update(script="verify_bad.py", expect_exit=0), 3)
        run("repro 输出 sha256 失配判 rc3",
            lambda c: c["repro"].update(expect_sha256="e" * 64), 3)
        # check_content(run_repro=False)：结构+哈希检查，不执行 repro 脚本。
        # 用带执行痕迹的脚本证明：validate 路径后 REPRO_EXECUTED 不应存在（未执行）。
        trace = clean()
        trace["repro"] = {"script": "verify_trace.py", "args": ["data.json"],
                          "expect_exit": 0, "expect_sha256": data_sha}
        terrors = []
        trc, _ = check_content(trace, d, terrors, run_repro=False)
        cases.append(("check_content(run_repro=False) 不执行 repro 脚本",
                      trc == 0 and not terrors and not os.path.exists(trace_marker), trc, 0))
        run("stage 非法被拦", lambda c: c.update(stage="sideways"), 1)
        run("doubt 非数组被拦", lambda c: c.update(doubt="not-list"), 1)
        run("doubt 项 kind 非法被拦",
            lambda c: c["doubt"][0].update(kind="lol"), 1)
        run("doubt 项缺 what 被拦",
            lambda c: c["doubt"][0].pop("what"), 1)
        run("doubt 项 stage 非法被拦",
            lambda c: c["doubt"][0].update(stage="bogus"), 1)
        run("doubt 项 since 非日期被拦",
            lambda c: c["doubt"][0].update(since="yesterday"), 1)
        run("anchor.sha256 失配本地文件判 rc3",
            lambda c: c["anchor"].update(sha256="f" * 64), 3)
        run("anchor 与 frozen 同文件哈希不一致判 rc3",
            lambda c: c["anchor"].update(sha256="e" * 64), 3)
        run("made_at 非日期被拦",
            lambda c: c.update(made_at="garbage"), 1)
        run("anchor.asof 非日期被拦",
            lambda c: c["anchor"].update(asof="garbage"), 1)
        run("anchor 未知字段被拦",
            lambda c: c["anchor"].update(bogus="x"), 1)
        run("frozen 未知字段被拦",
            lambda c: c["frozen"].update(bogus="x"), 1)
        run("repro 未知字段被拦",
            lambda c: c["repro"].update(bogus="x"), 1)
        run("repro.expect_exit 为 bool 被拦",
            lambda c: c["repro"].update(expect_exit=True), 1)
        run("doubt 项未知字段被拦",
            lambda c: c["doubt"][0].update(extra="x"), 1)
        run("doubt 项 what 为空被拦",
            lambda c: c["doubt"][0].update(what=""), 1)
        run("anchor frozen-bytes 文件缺失判 rc3",
            lambda c: c["anchor"].update(file="nope.bin"), 3)
        # 报告诚实性：rc3 时 content.pass=false、structure.pass=true、exit_code 与 pass 不矛盾
        c = clean()
        c["frozen"].update(sha256="f" * 64)
        p = os.path.join(d, "report_honesty.json")
        json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        rc, rep = verify_claim(p, d)
        honest = (rc == 3 and rep["checks"]["content"]["pass"] is False
                  and rep["checks"]["structure"]["pass"] is True
                  and rep["exit_code"] == 3 and rep["checks"]["content"]["errors"])
        cases.append(("报告诚实性：rc3 时 content.pass=false 且带错误明细",
                      honest, rc, 3))

        # 畸形 JSON：gate 必须返回 (rc=1, report)，不能 TypeError 崩溃
        bad_json = os.path.join(d, "bad.json")
        open(bad_json, "w", encoding="utf-8").write("not json{")
        rc, rep = verify_claim(bad_json, d)
        cases.append(("畸形 JSON 返回 rc1 且带报告（不崩）",
                      rc == 1 and isinstance(rep, dict) and rep["exit_code"] == 1,
                      rc, 1))
        # expect_exit 可选：schema 只 required script，缺 expect_exit 应通过
        run("repro 缺 expect_exit 通过（schema 可选）",
            lambda c: c["repro"].pop("expect_exit"), 0)
        # expect_sha256 等值而非子串：期望哈希被嵌在超长 hex 串里仍应判失配
        c = clean()
        c["repro"].update(script="sha_long.py", args=[], expect_exit=0,
                          expect_sha256="0" * 64)
        p = os.path.join(d, "sha_embed.json")
        json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        rc, _ = verify_claim(p, d)
        cases.append(("expect_sha256 等值匹配（超长 hex 串嵌入不算）", rc == 3, rc, 3))

        # expect_values：派生数值与脚本输出逐值锚定（回归守卫）
        # 1) 值匹配 + statement 含该值 → rc0
        c = clean()
        c["repro"].update(script="verify_val_ok.py", args=["data.json"],
                          expect_exit=0, expect_sha256=data_sha,
                          expect_values={"alt_km": "418.3"})
        c["statement"] = "轨道高度 418.3 km"
        p = os.path.join(d, "val_match.json")
        json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        rc, _ = verify_claim(p, d)
        cases.append(("expect_values 匹配 + statement 含值 → rc0", rc == 0, rc, 0))
        # 2) 脚本输出值不匹配声明 → rc3
        c = clean()
        c["repro"].update(script="verify_val_bad.py", args=["data.json"],
                          expect_exit=0, expect_sha256=data_sha,
                          expect_values={"alt_km": "418.3"})
        c["statement"] = "轨道高度 418.3 km"
        p = os.path.join(d, "val_mismatch.json")
        json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        rc, _ = verify_claim(p, d)
        cases.append(("expect_values 脚本输出值不匹配 → rc3", rc == 3, rc, 3))
        # 3) statement 不含该值（声明正文与脚本输出脱钩）→ rc3
        c = clean()
        c["repro"].update(script="verify_val_ok.py", args=["data.json"],
                          expect_exit=0, expect_sha256=data_sha,
                          expect_values={"alt_km": "418.3"})
        c["statement"] = "轨道高度 999.9 km"   # 突变：正文数字与脚本实际值矛盾
        p = os.path.join(d, "val_statement.json")
        json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        rc, _ = verify_claim(p, d)
        cases.append(("expect_values 值未在 statement 独立 token 出现（脱钩）→ rc3", rc == 3, rc, 3))
        # 4) 英文句尾句号是句子标点应放行（"The altitude is about 418.3." 不应被误杀）
        c = clean()
        c["repro"].update(script="verify_val_ok.py", args=["data.json"],
                          expect_exit=0, expect_sha256=data_sha,
                          expect_values={"alt_km": "418.3"})
        c["statement"] = "The altitude is about 418.3."
        p = os.path.join(d, "val_en_period.json")
        json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        rc, _ = verify_claim(p, d)
        cases.append(("expect_values 英文句尾句号放行 → rc0", rc == 0, rc, 0))

        # 历法校验：形状对但历法不存在必须拦
        run("made_at 历法非法被拦（2026-13-99）",
            lambda c: c.update(made_at="2026-13-99"), 1)
        run("made_at 闰年合法通过（2024-02-29）",
            lambda c: c.update(made_at="2024-02-29"), 0)
        run("anchor.asof 历法非法被拦（2026-02-30）",
            lambda c: c["anchor"].update(asof="2026-02-30"), 1)

        # supersedes 谱系链：指向不存在的 claim 必须拦
        run("supersedes 指向不存在 claim 被拦",
            lambda c: c.update(supersedes=["VC-19990101-999"]), 1)

        # text-quote 锚快照字节承诺——引用句须钉到冻结快照
        run_quote("text-quote 缺 snapshot 被拦",
                  lambda c: (c["anchor"].pop("snapshot"), c["anchor"].pop("snapshot_sha256")), 1)
        run_quote("text-quote snapshot_sha256 非 64 位被拦",
                  lambda c: c["anchor"].update(snapshot_sha256="short"), 1)
        run_quote("text-quote snapshot 文件缺失判 rc3",
                  lambda c: c["anchor"].update(snapshot="nope.html"), 3)
        run_quote("text-quote snapshot 哈希失配判 rc3",
                  lambda c: c["anchor"].update(snapshot_sha256="f" * 64), 3)
        run_quote("text-quote 引用句锚定快照通过（实体+渲染空格归一化）→ rc0",
                  lambda c: None, 0)
        run_quote("text-quote 引用句不在快照被判 rc3",
                  lambda c: c["anchor"].update(quote=snap_quote.replace("Yamasa", "YamasaX")), 3)

    sync_errors = check_schema_sync()
    cases.append(("schema-gate 契约同步（漂移守卫）",
                  not sync_errors, 0 if not sync_errors else 1, 0))
    for e in sync_errors:
        print("    schema 漂移: %s" % e)

    ok = True
    for name, passed, rc, want in cases:
        print("  %s  %s (rc=%d, want=%d)" % ("PASS" if passed else "FAIL", name, rc, want))
        ok = ok and passed
    if not ok:
        print("SELF-TEST FAILED（%d cases）" % len(cases))
        return 1
    print("SELF-TEST OK（%d cases）" % len(cases))
    return 0


# ---------- 命令分发 ----------

def cmd_verify(argv):
    args = list(argv)
    write_report = None
    if "--report" in args:
        i = args.index("--report")
        if i + 1 >= len(args):
            print("用法: verify_claim.py verify <claim.json> [--report out.json]"
                  "（--report 需带输出路径）", file=sys.stderr)
            return 2
        write_report = args[i + 1]
        del args[i:i + 2]
    if not args:
        print("用法: verify_claim.py verify <claim.json> [--report out.json]")
        return 2
    path = args[0]
    if not os.path.exists(path):
        print("文件不存在: %s" % path, file=sys.stderr)
        return 2
    rc, report = verify_claim(path, BASE)
    if write_report:
        with open(write_report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("报告已写入: %s" % write_report)
    return rc


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    cmd = argv[0]
    if cmd == "self-test":
        return cmd_self_test(argv[1:])
    if cmd == "verify":
        return cmd_verify(argv[1:])
    print("未知命令: %s" % cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

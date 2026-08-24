#!/usr/bin/env python3
# verify_iss.py — 验证 ISS 轨道衰减（零依赖）
# 输入：CelesTrak 公开 TLE（NORAD 25544 / ISS）
# 输出：轨道高度 / 周期 / 瞬时衰减速率 / 快照 sha256
# 用法：python3 verify_iss.py      （联网下载最新 TLE）
#       python3 verify_iss.py FILE  （用本地 TLE 文件）
# 退出码：0 成功；1 下载失败；2 解析失败
import hashlib
import sys
import urllib.request
from math import pi

MU = 398600.4418   # 地球引力常数 km^3/s^2
RE = 6378.137      # 地球赤道半径 km
CATNR = 25544      # ISS NORAD 编号
URL = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={CATNR}&FORMAT=TLE"


def fetch(path=None):
    if path:
        with open(path, "rb") as f:
            raw = f.read()
    else:
        req = urllib.request.Request(URL, headers={"User-Agent": "verifiable-claim-verify/1.0"})
        raw = urllib.request.urlopen(req, timeout=20).read()
    return raw


def parse_tle(raw):
    text = raw.decode("utf-8", errors="replace").splitlines()
    l1 = next((l for l in text if l.startswith("1 ")), None)
    l2 = next((l for l in text if l.startswith("2 ")), None)
    if not l1 or not l2:
        raise ValueError("TLE 格式无法解析")
    ndot = float(l1[33:43])       # rev/day^2
    mm = float(l2[52:63])         # rev/day
    return ndot, mm


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    raw = fetch(path)
    sha = hashlib.sha256(raw).hexdigest()

    try:
        ndot, mm = parse_tle(raw)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    period_min = 1440.0 / mm
    period_s = period_min * 60.0
    a = (MU * (period_s / (2 * pi)) ** 2) ** (1 / 3)   # 长半轴 km
    alt = a - RE                                        # 平均高度 km
    decay_km_day = -(2.0 / 3.0) * (a / mm) * ndot        # km/day

    print("=== ISS 轨道衰减验证（CelesTrak 公开 TLE，NORAD 25544）===")
    print(f"轨道高度      ≈ {alt:6.1f} km")
    # 结构化 label=value 行：供 gate 的 repro.expect_values 解析
    #（statement 数值与脚本实际值锚定）
    print(f"alt_km={alt:.1f}")
    print(f"轨道周期      ≈ {period_min:6.2f} min")
    print(f"瞬时衰减速率  ≈ {abs(decay_km_day) * 1000:5.0f} m/day"
          f"（≈ {abs(decay_km_day) * 30:4.1f} km/月）")
    print("-" * 46)
    print("证据层级: derived（可复现≠可验证；声明由锚源重算派生，非 primary 原始观测）")
    print("出处定位: CelesTrak 公开 TLE（NORAD 25544）——镜像自美国太空部队 18 空间防御")
    print("          中队官方编目（Space-Track），免费公开 API 获取")
    print("说明: 原始两行要素为官方编目（primary 锚源）；高度/周期/衰减速率由脚本从 TLE 重算，")
    print("          故本脚本产出的声明为 derived 层级")
    print("-" * 46)
    print(f"TLE 快照 sha256: {sha}")
    print("验证方式：任意时刻重跑本脚本，与文章正文数据表核对。")
    if path is None:
        print("注意: 本输出为【联网模式】当前实时值，随 ISS 缓慢再入逐日衰减；"
              "声明 418.3 km 对应冻结历元 2026-08-14（data/iss_20260814.tle），"
              "复现该值请带文件参数: python3 verify_iss.py data/iss_20260814.tle")
    return 0


if __name__ == "__main__":
    sys.exit(main())

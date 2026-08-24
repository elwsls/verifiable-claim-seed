---
title: 学术声明：「1 万步」的来龙去脉——两条可验证声明的人类可读报告
date: 2026-08-23
description: 人类可读概念样张·学术声明格式：把机器声明 VC-20260823-001（起源）/ VC-20260823-002（科学）渲染成研究者可读的声明报告，逐字引用句 + 定位 + doubt 表面 + stage 全挂上。对应机器 JSON，可由 verify_claim.py 机器核验。注意：verify_tier 是样张自身元数据，独立于对应机器声明的 schema tier（primary），不参与门禁。
verify_tier: derived
---

# 学术声明：「1 万步」的来龙去脉

> 本文为 verifiable-claim-seed 的人类可读概念样张（学术声明格式）：把下方两条机器声明逐字渲染成研究者可读的报告。**每条声明的真值由锚承担**（逐字引用句 + 定位，可回主源核）；doubt 表面列出「未验/存疑/局限」。机器核验：`python3 verify_claim.py verify claims/<file>.json`。

---

## 声明 VC-20260823-001：起源

**陈述（statement）**
「每天 1 万步」这一全球流行的健康目标，其数字并非来自医学证据，而是源自 1965 年前后日本 Yamasa Clock 公司为计步器 Manpo-kei（万歩計，意为"一万步计"）所做的营销命名——该数字自此作为每日步数目标扩散至全球。

**层级（tier）：primary**
> 锚即正确性载体：外部正确性由逐字引用句 + 定位承担，无需 repro/frozen。

**锚（anchor，text-quote）**
- 源：World Cancer Research Fund 博客《Do we really need to walk 10,000 steps a day?》，作者 Lindsay Bottoms（University of Hertfordshire 运动与健康生理学 Reader），2021-03-09 发布
- 逐字引用句（可回源核）：
  > "The 10,000 steps a day target seems to have come about from a trade name pedometer sold in 1965 by Yamasa Clock in Japan. The device was called “Manpo-kei”, which translates to “10,000 steps meter”. This was a marketing tool for the device and has seemed to have stuck across the world as the daily step target."
- 定位（locator）：https://www.wcrf.org/about-us/news-and-blogs/do-we-really-need-to-walk-10000-steps-a-day/
- 核验动作：打开定位，逐字比对引用句；缺失/失配即锚失效（外部正确性断裂）。

**doubt 表面（影子）**
| kind | what | stage |
|---|---|---|
| 未验 | 起源年份与厂商各家说法不一（1964/1965/1968 等），仅锚定 WCRF 一源，未穷尽全部版本；"Manpo-kei"确切营销动机未核一手档案 | growing |
| 局限 | 锚源为科普性二手综述，非一手商业史料；原文措辞 "seems to have come about" 本身即推测性表述 | settled |
| 存疑 | 部分来源将起源归于 1964 东京奥运健康风潮或不同厂商；需更多一手史料才能钉死单一版本 | growing |

**阶段（stage）：settled**（稳定存在——营销来历被多家来源记载，细节版本待钉死）

---

## 声明 VC-20260823-002：科学

**陈述（statement）**
步数与全因死亡风险呈非线性负相关：≥60 岁在 6000–8000 步/天后风险降低趋平，<60 岁在 8000–10000 步/天后趋平；"每天 1 万步"被广泛推广但缺乏证据支持（观察性研究，非因果）。

**层级（tier）：primary**

**锚（anchor，text-quote）**
- 源：Paluch AE 等，《Daily steps and all-cause mortality: a meta-analysis of 15 international cohorts》，Lancet Public Health 2022;7(3):e219-e228（Steps for Health Collaborative）
- 逐字引用句：
  > "Restricted cubic splines showed progressively decreasing risk of mortality among adults aged 60 years and older with increasing number of steps per day until 6000–8000 steps per day and among adults younger than 60 years until 8000–10 000 steps per day."
- 定位（locator）：doi:10.1016/S2468-2667(21)00302-9 · PMID 35247352 · PMC9289978
- 核验动作：检索 PMID 35247352 / DOI，逐字比对 FINDINGS 中该句；失配即锚失效。补充背景句（"Although 10 000 steps per day is widely promoted to have health benefits, there is little evidence to support this recommendation."）支撑"缺乏证据支持"部分。

**doubt 表面（影子）**
| kind | what | stage |
|---|---|---|
| 局限 | 观察性队列研究（meta 分析 15 队列 / 47471 成人），关联非因果，不能排除反向因果与混杂 | settled |
| 局限 | 步数测量依赖各队列设备协议，跨研究可比性有限；具体趋平数值随证据更新可能微调 | settled |
| 未验 | 2022 年发布，未纳入此后更新综述（如 2025 年 57 研究综述），最新趋平数值待核 | growing |

**阶段（stage）：settled**

---

## 与新闻稿的关系

`docs/news-release-10000-steps.md` 是这条故事的传播层；本文是信用层——新闻稿里引用的每一处数字与来历，都在这里给了逐字引用句 + 定位 + doubt 表面。**钩子再响，得有人能回主源核——这就是框架要治的病。**

## 机器核验

```sh
python3 verify_claim.py verify claims/VC-20260823-001.json   # 起源，期望 rc0
python3 verify_claim.py verify claims/VC-20260823-002.json   # 科学，期望 rc0
```

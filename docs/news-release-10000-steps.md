---
title: 你每天走的 1 万步，来自 1960 年代营销口号
date: 2026-08-23
description: 人类可读概念样张·新闻稿格式：把「1 万步」的来龙去脉写成一条真实新闻稿，并示范新闻稿自带 doubt 表面 + stage + 锚。verify_tier=derived——锚定 WCRF 科普源与 Paluch 2022（Lancet Public Health）研究，逐字引用句与定位见文末。注意：verify_tier 是样张自身元数据，独立于对应机器声明 VC-20260823-001/002 的 schema tier（primary），不参与门禁。
verify_tier: derived
---

# 你每天走的 1 万步，来自 1960 年代营销口号

> 本文为 verifiable-claim-seed 的人类可读概念样张（新闻稿格式）：示范一条新闻稿如何自带「声明带影子出厂」——文末挂本稿存疑、证据锚与阶段。verify_tier=derived，与机器声明 VC-20260823-001/002 对应。

**本刊讯（8 月 23 日）** 如果你今天也在为凑满"1 万步"而多走几步，这里有条你可能没听过的来历：这个数字不是医学结论，而是 1965 年前后一家日本钟表公司的营销命名。

## 这个数字从哪来？

故事要从一款计步器说起。日本 Yamasa Clock 公司在 1965 年推出一款名为 **Manpo-kei**（万歩計）的计步器，产品名直译就是"一万步计"。公司在推广时把它包装成"每天走 1 万步"的健康目标——一个好记、听起来又很有说服力的整数。

结果这个营销数字在全世界扎了根。世界癌症研究基金会（WCRF）2021 年的一篇科普文章记录了这一来历：

> The 10,000 steps a day target seems to have come about from a trade name pedometer sold in 1965 by Yamasa Clock in Japan. The device was called “Manpo-kei”, which translates to “10,000 steps meter”. This was a marketing tool for the device and has seemed to have stuck across the world as the daily step target.

今天，智能手表、运动 App、健身博主，都在以"1 万步"为每日默认目标——而它最初只是为卖一款计步器而生的口号。

## 那么科学怎么说？

数字是营销，但"多走路对身体好"本身有证据。2022 年《柳叶刀·公共卫生》发表的一项 meta 分析（15 个国际队列、47,471 名成人）给出了更具体的图景：

> Restricted cubic splines showed progressively decreasing risk of mortality among adults aged 60 years and older with increasing number of steps per day until 6000–8000 steps per day and among adults younger than 60 years until 8000–10 000 steps per day.

翻译成大白话：**步数越多、全因死亡风险越低，但这种降低不是无限的**——60 岁以上人群在每天 6000–8000 步后，风险降低就趋平了；60 岁以下人群大约在 8000–10000 步后趋平。也就是说，对大多数人而言，"1 万步"是一个好记但不必要的目标，一半的量可能就够了。

## 为什么这值得你停下来想一下？

因为它是一个最日常的样本，指向一个普遍现象：**我们天天在信的数字，未必知道它从哪来、可信在哪、可疑在哪。**

"1 万步"是营销起源，但有科学支撑它的近似值；这个数字的"影子"（营销来历、证据趋平点、观察性研究的局限）一直存在，只是没有人把影子亮出来。如果数字自带影子——它怎么来的、证据是什么、还有哪些没核实——你就不用靠运气判断该不该信。

这就是本稿示范的姿态：**一条新闻稿，也声明它知道自己的数字从哪来、可疑在哪。**

## 本稿存疑（doubt 表面）

> - **起源年份与厂商各家说法不一**：本稿锚定 WCRF 一源（1965 / Yamasa Clock），其他来源有 1964、1968 等版本；"为何偏偏选 1 万这个数"未核一手商业档案。
> - **"1 万步是营销"依赖二手综述**：WCRF 博客是科普性二手源，其原文措辞 "seems to have come about" 本身就是推测性表述；一手史料待补。
> - **步数-死亡关联是观察性研究**：meta 分析非随机试验，关联非因果；具体趋平数值（6000-8000 等）随证据更新可能微调，本稿未纳入 2022 年后的新综述。

## 证据锚（逐字引用句 + 定位）

- 起源：WCRF 博客，Lindsay Bottoms（University of Hertfordshire），2021-03-09 — [Do we really need to walk 10,000 steps a day?](https://www.wcrf.org/about-us/news-and-blogs/do-we-really-need-to-walk-10000-steps-a-day/)
- 科学：Paluch AE 等，Lancet Public Health 2022;7(3):e219-e228 — doi:10.1016/S2468-2667(21)00302-9 · PMID 35247352
- 机器声明：`claims/VC-20260823-001.json`（起源）、`claims/VC-20260823-002.json`（科学），`python3 verify_claim.py verify <file>` 可核

## 阶段

- **起源部分：settled**（已稳定——营销来历被多家来源记载，但细节版本待钉死）
- **科学部分：settled**（已稳定——趋平结论在 2022 综述内一致，最新证据待跟进）

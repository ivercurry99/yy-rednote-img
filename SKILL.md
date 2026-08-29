---
name: yy-text2-xhs-img
description: "结构化 Prompt + 多模型适配器，一键生成小红书封面和正文配图。用户需要稳定、风格一致的小红书 AI 生图时使用；支持 TRAE 内置、Seedream 插件、DALL·E 3、FLUX 多模型自动降级，内置 8 种小红书风格预设与负面词库。"
license: MIT
version: 1.0.0
author: ivercurry99
triggers:
  - "小红书生图"
  - "小红书配图"
  - "xhs 配图"
  - "小红书 AI 封面"
  - "生成小红书图片"
  - "生成小红书封面"
  - "yy text2 xhs"
  - "text2 xhs img"
---

# yy-text2-xhs-img · 小红书 AI 图文生成技能

把用户的一句话需求，转化成**风格稳定、可复现、可降级**的小红书出图流水线。不再靠运气每次"摇骰子"，而是：

1. **锁死 Prompt 结构**：结构化 Schema + 8 套风格预设 JSON，调色板/构图/灯光/镜头每一项都固定；
2. **多路模型分发**：TRAE 内置 → Seedream 插件 → DALL·E 3 → FLUX，自动降级，一路成功即出图；
3. **每张图片都做 QA**：PNG 文件头、最小体积、比例容差三项检查，失败自动重试最多 3 次；
4. **写 manifest.json 清单**：记录模型/种子/Prompt/预设，任何一次出图都能精确复现。

> 本技能专注 **AI 文生图**。如果需要 HTML 模板渲染卡片（比如带排版的知识卡片），请使用 `xhs-note-creator`。

---

## 核心特性

| 常见痛点 | 本技能的解法 |
|---|---|
| 两次生图之间颜色/镜头/风格漂移严重 | **8 套预设 JSON** 锁死调色板、构图、灯光、氛围、镜头 |
| 一个模型限流就全挂了 | **4 路供应商降级链**，任意一路可用就能出图 |
| 忘写负面词 → 水印/六指/畸形字 | **小红书负面词库**（30+ 条）每次自动追加 |
| 比例错了，小红书首页裁切 | **比例映射** 锁定 3:4 / 1:1 / 4:3 / 9:16，按模型原生尺寸出图 |
| 生成的文件损坏/是空壳 | **完整性校验**：PNG magic + ≥50KB + 比例误差≤1%，失败自动重跑 |
| 一张好图下次怎么都出不来 | **manifest.json** 记录每张图的模型、种子、Prompt、预设 |

---

## 标准 5 步工作流

### 第 1 步 — 结构化收集需求

不要写长句。先把用户的意图拆成字段：

| 字段 | 是否必填 | 含义 | 示例 |
|---|---|---|---|
| `topic` | 是 | 笔记主题，受众 + 主体都写进去 | "20+ 夏天油皮护肤三步曲" |
| `card_count` | 是 | 总张数（含封面），一般 4 张（1 封面 + 3 正文） | `4` |
| `style_preset` | 是 | 8 套预设中选一个（见下节） | `ins-aesthetic` |
| `ratio` | 是 | `3:4` / `1:1` / `4:3` / `9:16`，小红书首页默认 3:4 | `3:4` |
| `emoji_mood` | 否 | 情绪关键词，翻译为氛围形容词 | "清新、奶油、治愈" |
| `keywords` | 否 | 视觉/SEO 关键词，具体物体和材质 | "防晒霜、膏体涂抹、滴管特写" |
| `audience` | 否 | 目标人群，影响肤色/穿搭/年龄 | "20-30 岁东亚女生" |
| `has_text` | 否 | 画面里要放清晰文字？默认 `false`（多数模型写不出合格中文），为 true 时切到 dalle3 | `false` |
| `reference_style` | 否 | 自由风格补充提示 | "日系 VIVI 杂志风" |
| `exclude` | 否 | 额外负面词，会拼到统一负面词里 | "不露脸、不要模特" |

如果用户没有说可选字段，直接选合理默认值，最后回复时告诉用户你做了哪些假设，不要来回追问。

### 第 2 步 — 选风格预设（8 套内置）

| 预设名 | 视觉印象 | 最适合 |
|---|---|---|
| `ins-aesthetic` | 奶白色调 + 柔光窗边 + 低对比 + 20% 留白 | 护肤 / 穿搭 / 生活方式 |
| `clean-minimal` | 纯白无缝 + 俯视平铺 + 主体居中 + 硬接触阴影 | 美妆 / 电商 / 单品主图 |
| `neo-chinese` | 朱砂红 + 24K 金 + 水墨晕染 + 国潮纹样 | 节日 / 茶饮 / 文创 / 口红 |
| `y2k-funky` | 高饱和 + 铬金属 + 品红青蓝 + 闪光灯 + 千禧感 | 校园 / Z世代 / 潮流 / 夏日 |
| `magazine-editorial` | Vogue 大片 + 35mm Portra 胶卷颗粒 + 三分法 + 左侧文案区 | 深度笔记 / 观点文 / 高定穿搭 |
| `emotional-daily` | 黄金时段暖色 + 手持抓拍 + Kodak Gold 200 颗粒 + 松弛 | 美食日记 / 探店 / 旅行 / 情绪风 |
| `product-flatlay` | 正 90° 俯视 + 麻布/牛皮纸背景 + 少量道具点缀 | 开箱 / 好物合集 / 步骤展示 |
| `cute-illustration` | 扁平矢量 + 圆润粗描边 + 三丽鸥马卡龙柔和色 | 知识卡片 / 教程 / 儿童教育 |

> 预设定义在 `styles/presets.json` 中，按照同样的 Schema 可以继续追加自定义预设。

### 第 3 步 — 运行生成器

```bash
# 默认 & 推荐（不需要 API Key，优先用 TRAE 内置生图）
python scripts/generate.py ^
  --topic "20+ 夏天油皮护肤三步曲" ^
  --cards 4 ^
  --style ins-aesthetic ^
  --ratio 3:4

# 显式指定降级顺序（每一路失败会自动切到下一路）
python scripts/generate.py ^
  --topic "七夕节国潮口红开箱合集" ^
  --cards 5 ^
  --style neo-chinese ^
  --ratio 3:4 ^
  --providers trae-native,seedream-plugin,dalle3

# 真的要用 DALL·E 3 或 FAL FLUX 时，先配置环境变量
# 详见 references/fallback-strategy.md
# export OPENAI_API_KEY=sk-xxx
# export FAL_KEY=xxxx:xxxx

# 仅打印 Prompt，不调用 API（先看结构，避免浪费额度）
python scripts/generate.py ^
  --topic "先空跑看下" --cards 1 --style magazine-editorial --ratio 3:4 ^
  --dry-run-prompts
```

**输出目录结构**（每次运行生成独立的时间戳目录）：

```
output/20260829-200215-abc123/
├── cover.png
├── card_1.png  card_2.png  card_3.png
├── manifest.json      ← 模型 / 种子 / Prompt / 预设 记录
└── _failed/           ← 重试过程中丢弃的损坏图片
```

### 第 4 步 — 自动 QA（每次都跑）

生成完成后，脚本会自动检查（不通过 → 该张图重试）：

- [x] 文件存在 AND 大小 ≥ 50 KB
- [x] PNG 文件头 `\x89PNG` 匹配（拒绝截断/损坏）
- [x] 张数和 `--cards` 一致
- [x] 图片宽高比例误差 < 1%（用 Pillow 回读 W/H）

同一供应商连续 3 次失败 → 自动切换到降级链中的下一家。

### 第 5 步 — 交付结果 + 保留 manifest

交付时一定要告诉用户：

1. 产出了多少张图，运行目录在哪里；
2. 最终成功的是**哪个预设 + 哪个供应商**，方便用户下次直接复用这套组合；
3. `manifest.json` 在哪，方便以后复现某张好图。

---

## 供应商适配器概览

完整说明见：`references/fallback-strategy.md`（降级链 & Key 配置）和 `references/model-matrix.md`（模型选型矩阵）。

| 供应商 ID | 需要的环境/凭据 | 优势 | 何时选 |
|---|---|---|---|
| `trae-native` | 宿主暴露了 `GenerateImage` 工具 | **零配置、免费**，默认第一选择 | 默认 #1 |
| `seedream-plugin` | TRAE Seedream 插件已授权 | 电影级调色，中文元素友好，速度快 | TRAE 环境内 |
| `dalle3` | 环境变量 `OPENAI_API_KEY` | 唯一能稳定画出**清晰中文文字**的一家 | `has_text=true` 时必用 |
| `fal-flux` | 环境变量 `FAL_KEY` | 细节最丰富，人体结构最稳，风格锁定最强 | 高质量营销图 / 风格化强的场景 |

**默认降级顺序**（可用 `--providers` 覆盖）：
`trae-native → seedream-plugin → dalle3 → fal-flux`

---

## 仓库结构

```
yy-text2-xhs-img/
├── SKILL.md                    # 智能体行为规范（本文件）
├── README.md                   # 面向用户的 GitHub 项目说明
├── LICENSE                     # MIT 许可证
├── requirements.txt            # 可选 Python 依赖（Pillow + 可选 API 客户端）
├── styles/
│   └── presets.json            # 8 套风格预设 + 负面词库 + 尺寸比例映射
├── scripts/
│   └── generate.py             # 主脚本：Schema → Prompt → 多模型分发 → 校验 → 清单
├── references/
│   ├── prompt-engineering.md   # 小红书 Prompt 工程手册
│   ├── model-matrix.md         # 模型选型对比矩阵
│   └── fallback-strategy.md    # 降级链设计 + API Key 配置指南
├── tests/
│   └── test_generate.py        # 单元测试（Prompt 拼接、尺寸映射、重试逻辑），全部走 mock
├── evals/
│   └── evals.json              # 回归评测用例集
└── .github/workflows/ci.yml    # CI：pytest + presets.json 结构校验 + 语法检查
```

---

## 触发词（供智能体路由匹配）

- "小红书生图"、"小红书配图"、"xhs 配图"
- "生成小红书封面"、"小红书 AI 封面"
- "text2 xhs img"、"yy text2 xhs"
- "帮我画 4 张小红书护肤图" / 任意包含「小红书 + 图片」的组合意图

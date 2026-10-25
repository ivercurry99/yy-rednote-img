---
name: yy-rednote-img
description: "把一段中文文字排成可以直接发布的小红书图文（封面加正文），也可以按风格预设调用 AI 配图，配图效果取决于所用模型。用户说「文字转图文」「小红书图文」「知识卡片」「小红书配图」时使用。"
license: MIT
version: 1.1.0
author: ivercurry99
triggers:
  - "小红书图文"
  - "文字转图文"
  - "小红书知识卡片"
  - "小红书生图"
  - "小红书配图"
  - "xhs 配图"
  - "生成小红书封面"
  - "yy rednote img"
  - "rednote img"
---

# yy-rednote-img · 文字 → 小红书图文

把用户给的一段文字，排成 1080×1440、可以直接发小红书的一组卡片：封面 + 若干张正文。中文由系统字体排版，不经过图像模型，所以不会出现错字、糊字、乱码。

如果用户还需要照片感或插画感的封面，同一仓库里另有一套 AI 配图流水线（8 套风格预设 + 4 路供应商降级）。

---

## 先判断走哪条路

| 用户给了什么 | 走哪条 | 用哪个脚本 |
|---|---|---|
| 一段文案、要点、教程、科普、书摘 | **文字卡片**（默认） | `scripts/card.py` |
| 只说「画一张/几张封面图」，没有具体文字要排 | AI 配图 | `scripts/generate.py` |
| 想要文字卡正文 + AI 封面 | 两条都用，先排卡再出封面 | 两个脚本 |

用户说「做成图文」「排版」「知识卡」「把这段文字变成图片」时，一律先走 `card.py`。不要用 AI 模型去画中文文字。

---

## 路线 A — 文字卡片（默认）

### A1. 把用户的内容拆成 JSON

每张卡片一个对象，第一张默认是封面：

| 字段 | 必填 | 含义 |
|---|---|---|
| `title` | 是 | 卡片主标题，尽量 6–14 个字 |
| `type` | 否 | 第一张写 `cover`；其余可省略 |
| `kicker` | 否 | 左上角小标签，如「方法 01」 |
| `subtitle` | 否 | 封面副标题 |
| `lead` | 否 | 正文段落，`\n` 表示换行 |
| `bullets` | 否 | 编号列表，字符串数组，3–5 条为宜 |
| `callout` | 否 | 底部金句框 |
| `author` | 否 | 顶层字段，底部署名 |

没有给的内容不要编。用户只给了标题，就只排标题；缺的部分如实告诉用户还需要什么。

### A2. 选主题

| `--theme` | 观感 | 适合 |
|---|---|---|
| `ins-aesthetic` | 奶白底、棕调 | 生活方式 · 日常分享 |
| `clean-minimal` | 纯白、黑白灰 | 极简 · 工具 · 干货 |
| `neo-chinese` | 朱砂红 + 描金 | 节日 · 传统文化 |
| `y2k-funky` | 浅紫 + 荧光粉 | 潮流 · 校园 |
| `magazine-editorial` | 米灰底 + 宋体 | 书评 · 影评 · 长文 |
| `emotional-daily` | 暖黄 + 陶土色 | 日记 · 旅行 · 情绪 |
| `product-flatlay` | 亚麻灰 + 橄榄绿 | 好物 · 清单 |
| `cute-illustration` | 粉底 + 大圆角 | 教程 · 儿童 · 知识卡 |

用户没说就按内容气质选一个，并在交付时说明你选了哪个。主题色值在 `scripts/card.py` 的 `THEMES` 中。

### A3. 渲染

```bash
python scripts/card.py --input content.json --out output/cards --theme ins-aesthetic
```

- 依赖：Python 3.10+ 和本机 Chrome / Edge，不需要装任何 Python 包
- 找不到浏览器时用 `CHROME_PATH` 指定路径
- 产物：`cover.png`、`card_1.png`……，以及 `_html/` 中间文件
- 每张图渲染后都会校验 PNG 文件头和真实宽高，尺寸不对直接报错，不会交付坏图

### A4. 交付前检查

- 打开至少一张成品，确认标题没有被截断、没有溢出
- 标题过长时脚本会自动降字号；如果还是觉得挤，是内容本身太长，建议用户拆成两张
- 告诉用户：产出了几张、主题是什么、文件在哪

---

## 路线 B — AI 配图（可选）

用于用户明确要「照片感/插画感」的封面，且画面里不需要排中文。

### B1. 参数

| 字段 | 必填 | 含义 | 示例 |
|---|---|---|---|
| `topic` | 是 | 主题，受众 + 主体都写进去 | "20+ 夏天油皮护肤三步曲" |
| `card_count` | 是 | 总张数（含封面） | `4` |
| `style_preset` | 是 | 8 套预设选一个 | `ins-aesthetic` |
| `ratio` | 是 | `3:4` / `1:1` / `4:3` / `9:16` | `3:4` |
| `keywords` | 否 | 具体物体和材质 | "防晒霜、膏体涂抹" |
| `audience` | 否 | 目标人群 | "20-30 岁东亚女生" |
| `mood` | 否 | 情绪关键词 | "清新、治愈" |
| `exclude` | 否 | 额外负面词 | "不露脸、不要模特" |

### B2. 预设

| 预设名 | 视觉印象 | 最适合 |
|---|---|---|
| `ins-aesthetic` | 奶白色调 + 柔光窗边 + 低对比 | 护肤 / 穿搭 / 生活方式 |
| `clean-minimal` | 纯白无缝 + 俯视平铺 + 硬阴影 | 美妆 / 电商 / 单品 |
| `neo-chinese` | 朱砂红 + 24K 金 + 水墨 | 节日 / 茶饮 / 文创 |
| `y2k-funky` | 高饱和 + 铬金属 + 闪光灯 | 校园 / Z 世代 / 潮流 |
| `magazine-editorial` | 胶片颗粒 + 大片布光 + 文案区 | 深度笔记 / 观点文 |
| `emotional-daily` | 黄金时段 + 抓拍 + 颗粒 | 美食 / 探店 / 旅行 |
| `product-flatlay` | 正俯视 + 麻布背景 | 开箱 / 合集 / 步骤 |
| `cute-illustration` | 扁平矢量 + 圆角粗描边 | 知识卡插图 / 教程 |

完整 Schema 见 `styles/presets.json`。

### B3. 运行

```bash
# 先空跑看 Prompt，不花额度
python scripts/generate.py --topic "夏天油皮护肤三步曲" --cards 4 --style ins-aesthetic --ratio 3:4 --dry-run-prompts

# 正式生成（默认走 TRAE 内置 → Seedream → DALL·E 3 → FLUX）
python scripts/generate.py --topic "夏天油皮护肤三步曲" --cards 4 --style ins-aesthetic --ratio 3:4
```

### B4. 自动 QA

- 文件存在且 ≥ 50 KB
- PNG 文件头匹配，拒绝截断文件
- 宽高比例误差 < 1%
- 同一供应商连续失败 3 次 → 自动切到下一家

产物在 `output/<run-id>/`，其中 `manifest.json` 记录每张图的供应商、种子、Prompt 和预设，可用于复现。

---

## 供应商适配器

| 供应商 ID | 需要什么 | 何时选 |
|---|---|---|
| `trae-native` | 宿主暴露 `GenerateImage` | 默认首选，零配置 |
| `seedream-plugin` | TRAE Seedream 插件已授权 | TRAE 环境内 |
| `dalle3` | `OPENAI_API_KEY` | 需要画面里有英文文字时 |
| `fal-flux` | `FAL_KEY` | 细节和人体结构要求高时 |

详见 `references/fallback-strategy.md` 和 `references/model-matrix.md`。

---

## 仓库结构

```
yy-rednote-img/
├── SKILL.md                    # 智能体行为规范（本文件）
├── README.md                   # 面向用户的项目说明
├── LICENSE                     # MIT
├── requirements.txt            # AI 配图的可选依赖
├── templates/
│   └── card.html               # 文字卡片模板（改这里就能改版式）
├── scripts/
│   ├── card.py                 # 文字 → 图文卡片（主路径）
│   └── generate.py             # AI 配图（可选路径）
├── examples/                   # 可直接跑的内容 JSON 示例
├── styles/presets.json         # 8 套 AI 风格预设 + 负面词 + 尺寸映射
├── references/                 # Prompt 工程 / 模型矩阵 / 降级策略
├── tests/                      # 单元测试，全部离线
└── .github/workflows/ci.yml    # CI：pytest + 预设结构校验
```

---

## 触发词

- "小红书图文"、"文字转图文"、"小红书知识卡片"
- "把这段文字做成小红书图片"、"排成图文"
- "小红书配图"、"小红书封面"、"xhs 配图"
- "rednote img"、"yy rednote img"

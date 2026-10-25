# yy-rednote-img

![把一段文字，排成能直接发的小红书图文](assets/hero.png)

![License](https://img.shields.io/badge/license-MIT-green) ![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![CI](https://github.com/ivercurry99/yy-rednote-img/workflows/ci.yml/badge.svg)

把一段文字排成能直接发的小红书图文。标题、要点、金句给你排成 1080×1440 的卡片，中文由系统字体渲染，不会出现错字和糊字。需要配图时，再用内置的 8 套风格预设调 AI 出图。

## 示例

下面两组是作者之前实际发布过的图文，版式出自同一类 HTML 排版流程。左边的封面负责拦住人，右边三张讲清一件事。

**心理学效应 · 32 个定律（上篇）**

| 封面 | 01 墨菲定律 | 02 沉没成本 | 03 幸存者偏差 |
|---|---|---|---|
| ![封面：改变你决策的 32 个心理学效应](assets/showcase-psychology/00-cover.png) | ![墨菲定律](assets/showcase-psychology/01-murphy-law.png) | ![沉没成本](assets/showcase-psychology/02-sunk-cost.png) | ![幸存者偏差](assets/showcase-psychology/03-survivor-bias.png) |

**DeepSeek V4 API 全拆解**

| 封面 | 01 两大模型怎么选 | 02 深度思考模式 | 03 快速上手 |
|---|---|---|---|
| ![封面：DeepSeek API 全拆解](assets/showcase-deepseek/00-cover.png) | ![V4-Flash 与 V4-Pro 对比](assets/showcase-deepseek/01-two-models.png) | ![深度思考模式](assets/showcase-deepseek/02-thinking-mode.png) | ![快速上手](assets/showcase-deepseek/03-quick-start.png) |

`examples/` 里有 4 份可以直接跑的 `content.json`，渲染出来是同一套模板的卡片。

## 两条路线

**文字卡片（`scripts/card.py`）**：你给标题和要点，脚本写 HTML、调用本机 Chrome / Edge 无头模式截图。中文排版精确，字号会按标题长度自动挑，放不下就换字号，不会溢出。

**AI 配图（`scripts/generate.py`）**：需要照片感、插画感的封面时用。8 套预设锁定调色板、构图、灯光，4 家出图接口按顺序降级，每张图落地前检查 PNG 文件头、体积和比例。

两条路线可以混用：文字卡当正文，AI 图当封面。

## 安装

```text
请从此 URL 安装 Skill：https://github.com/ivercurry99/yy-rednote-img
```

或者：

```bash
npx skills add ivercurry99/yy-rednote-img
git clone https://github.com/ivercurry99/yy-rednote-img.git <你的技能目录>/yy-rednote-img
```

文字卡片只需要 Python 3.10+ 和本机已有的 Chrome 或 Edge，不需要装任何 Python 包。找不到浏览器时，用 `CHROME_PATH` 指定可执行文件路径。

## 写一份内容

新建 `content.json`：

```json
{
  "author": "@你的小红书号",
  "cards": [
    {
      "type": "cover",
      "kicker": "早起",
      "title": "3 个让早起变简单的方法",
      "subtitle": "不靠意志力，靠前一天晚上的设计"
    },
    {
      "kicker": "方法 01",
      "title": "先固定起床，再倒推睡觉",
      "lead": "把起床时间定死，连续记三天，你会知道自己实际需要几个小时。",
      "callout": "影响作息的关键变量是起床时间，不是入睡时间。"
    },
    {
      "kicker": "方法 02",
      "title": "把早上的第一个动作做小",
      "bullets": ["拉开窗帘", "喝一杯水", "不要先看手机"]
    }
  ]
}
```

字段说明：第一张默认按封面排版（大标题 + 副标题），后面的卡片支持 `lead` 段落、`bullets` 编号列表、`callout` 金句框。

渲染：

```bash
python scripts/card.py --input content.json --out output/cards --theme ins-aesthetic
```

产物：

```text
output/cards/
├── cover.png
├── card_1.png
├── card_2.png
└── _html/          # 中间 HTML，想手改样式就改这里
```

## 可用主题

| `--theme` | 观感 | 适合 |
|---|---|---|
| `ins-aesthetic` | 奶白底、棕调强调色 | 生活方式 · 护肤 · 日常分享 |
| `clean-minimal` | 纯白、黑白灰 | 极简 · 工具 · 干货 |
| `neo-chinese` | 朱砂红底 + 描金 | 节日 · 传统文化 · 茶与酒 |
| `y2k-funky` | 浅紫底、荧光粉 | 潮流 · 校园 · 年轻向 |
| `magazine-editorial` | 米灰底、宋体、砖红 | 书评 · 影评 · 长文 |
| `emotional-daily` | 暖黄底、陶土色 | 日记 · 旅行 · 情绪 |
| `product-flatlay` | 亚麻灰底、橄榄绿 | 好物 · 清单 · 开箱 |
| `cute-illustration` | 粉底、圆角大 | 教程 · 儿童 · 知识卡 |

主题定义在 `scripts/card.py` 的 `THEMES` 里，改一组色值就能加自己的风格。

## AI 配图（可选）

```bash
# 先空跑看 Prompt，不花额度
python scripts/generate.py --topic "夏天油皮护肤三步曲" --cards 4 --style ins-aesthetic --ratio 3:4 --dry-run-prompts

# 正式生成
python scripts/generate.py --topic "夏天油皮护肤三步曲" --cards 4 --style ins-aesthetic --ratio 3:4
```

8 套风格预设、4 路供应商降级（TRAE 内置 → Seedream → DALL·E 3 → FLUX）、比例映射和图片校验都在 `references/` 里写清楚了。只有用 API 模式直连 DALL·E 3 / FLUX 时才需要配 Key。

## 测试

```bash
pytest tests/ -v
```

`tests/test_card.py` 覆盖字号计算、HTML 转义、内容校验和 PNG 尺寸检查，不依赖浏览器；`tests/test_generate.py` 覆盖 Prompt 拼接、尺寸映射和降级链，全部离线。

## 许可证

MIT © 2026 ivercurry99

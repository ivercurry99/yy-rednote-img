<p align="center">
  <strong><samp>yy-text2-xhs-img</samp></strong><br>
  <sub>简短文本生成小红书图文 · 风格预设固定 · 出图接口故障时自动切换</sub>
</p>

<p align="center">
  <a href="#项目简介"><kbd>项目简介</kbd></a>
  <a href="#为什么能做到稳定出图"><kbd>稳定性设计</kbd></a>
  <a href="#八套内置风格预设"><kbd>8 套预设</kbd></a>
  <a href="#安装方式"><kbd>安装</kbd></a>
  <a href="#快速上手"><kbd>快速上手</kbd></a>
  <a href="#路线图与贡献"><kbd>路线 & 贡献</kbd></a>
  <a href="#许可证"><kbd>许可证</kbd></a>
</p>

---

## 项目简介

`yy-text2-xhs-img` 接收简短文本需求（例如「夏天油皮护肤三步曲，做 4 张小红书配图」），输出 3:4 或其他常用比例的图片文件。调用出图接口前，各家供应商的尺寸映射、调色板、构图规则和风格负面词都由预设文件确定，避免每次调用都重新编写提示词。

核心脚本 `scripts/generate.py` 处理了以下几类实际问题：

| 常见痛点 | 本仓库的解法 |
|---|---|
| 🎨 同一次出图里卡片之间颜色/风格飘了 | **8 套风格预设 JSON** — 经过小红书实测的造型手册，调色板 5 色锁定、构图、灯光、氛围、镜头 + 反风格负面词一应俱全。 |
| ⛔ 水印 / 畸形人体 / 乱码文字 | **通用负面词库（30+ 条）** + 预设专属负面词 + 用户自定义负面词，**每一次**调用全部分层叠加。 |
| 🚦 一个供应商挂了 → 整篇笔记卡住 | **4 路供应商降级链**：TRAE 内置 → Seedream 插件 → DALL·E 3 → FLUX。每家最多重试 3 次、指数退避；全挂再切下一家。 |
| 📏 小红书首页比例不对，被硬裁切 | **固定 sizeMap**：3:4 / 1:1 / 4:3 / 9:16 对应各家供应商最接近的原生尺寸桶。 |
| 🚫 损坏/截断图片悄悄发出去了 | **每张图必检**：PNG Magic 头 + 50 KB 下限 + 比例容差 < 1%；失败自动重试，不合格文件移入 `_failed/`。 |
| 🔁 "上周那篇出图效果好，想一模一样再来一次" | **manifest.json** 记录每张卡片的供应商 ID、种子、Prompt、预设、尺寸 — 重新执行即可 1:1 复现。 |

支持两种运行模式，无论你是在智能体宿主（TRAE / Codex / Claude Desktop 的 skills 目录）里跑，还是在 Shell 中直接调 API，走的都是同一套核心逻辑：

- **智能体模式（默认）**：先写一份 `tasks.json` 描述每张卡片；宿主调用自带的 `GenerateImage` / Seedream 插件把 PNG 丢进运行目录；脚本二次校验 + 写 manifest。
- **API 模式（`--mode api`）**：环境变量存在 Key 时，脚本直接调 OpenAI DALL·E 3 / FAL FLUX 生成。

---

## 为什么能做到稳定出图？

因为**一致性才是小红书笔记的产品力**。读者在刷 4 张 carousel 的时候，如果第 1 张是奶油 INS 风、第 2 张突然跳成 Y2K 铬金属，他在看到 CTA 之前就会划走。脚本强制用一套严格的 **Prompt 拼接顺序**：主体还原 → 构图 → 灯光 → 氛围 → 调色板锁定 → 场景具象化 → 角色定位，**之后**再给封面/步骤卡/过渡卡/收尾图拼上各自的角色话术。

在此之上，你仍然可以通过 CLI 参数自由定制：

```
--keywords "道具1, 道具2, 材质3"
--audience "20-28 岁东亚女生"
--mood "治愈、软糯、奶油马卡龙"
--exclude "不露脸、不要手"
--extra-prompt-suffix "品牌一致性规则：圆形点缀、烫金线条"
```

所有核心逻辑都是纯函数并经过单测，库里不会偷偷播种随机数。

---

## 八套内置风格预设

每套预设都是调优、锁死、并且**小红书原生适配**过的造型手册，都包含 **5 色调色板**、**4+ 条构图规则**、**4+ 条灯光规则**、**氛围 + 镜头 + 质量增强 + 反风格负面词**：

| `--style` | 视觉印象 | 最适合 |
|---|---|---|
| `ins-aesthetic` | 奶白 + 50mm 柔光窗边 + 低对比 + 留白柔和 | 护肤 · 穿搭平铺 · 生活方式 |
| `clean-minimal` | 100% 纯白无缝 + 俯视对称 + 硬接触阴影 | 单品主图 · 美妆 · 电商画册 |
| `neo-chinese` | 朱砂红 + 24K 金 + 水墨晕染 + 国潮纹样 | 节日 · 茶饮 · 口红 · 文创 |
| `y2k-funky` | 品红/青蓝 铬金属 + 闪光灯过曝 + 珠光亮面 | Z世代 · 校园 · 潮流 · 夏日选题 |
| `magazine-editorial` | Portra 400 颗粒 + 大片 3 灯布光 + 三分法 + 30% 安全文案区 | 深度长文 · 观点笔记 · 高定穿搭 |
| `emotional-daily` | 黄金时段暖色 + 35mm 抓拍 + 胶卷重颗粒 + 生活切片 | 美食日记 · 探店 · 旅行情绪 |
| `product-flatlay` | 正 90° 平铺 + 麻布/牛皮纸背景 + 道具同色系点缀 | 合集 · 开箱 · 护肤步骤 · 拆箱 |
| `cute-illustration` | 粗边圆润描边 + 三丽鸥马卡龙色 + 扁平矢量 | 知识卡片 · 教程 · 儿童教育 |

完整 Schema 见 `styles/presets.json`；如何追加自定义预设详见 `references/prompt-engineering.md` 第 7 节。

---

## 安装方式

### 1. 作为智能体 Skill 安装

把下面这句话发给任意支持 Skill 的智能体（TRAE、Claude Desktop、Alma、Codex…）：

```text
请从此 URL 安装 Skill：https://github.com/ivercurry99/yy-text2-xhs-img
```

如果你本机有 `skills` CLI：

```bash
npx skills add ivercurry99/yy-text2-xhs-img
```

也可以手动克隆到你的技能目录：

```bash
# 常见宿主目录，根据你自己的软件改：
#   TRAE:       ~/.trae/skills/   (Windows: %USERPROFILE%\.trae\skills\)
#   Claude:     ~/.claude/skills/
#   Alma:       ~/.config/Alma/skills/
git clone https://github.com/ivercurry99/yy-text2-xhs-img.git <your-skills-dir>/yy-text2-xhs-img
```

### 2. 安装可选 Python 依赖（仅 `--mode api` 需要）

```bash
cd yy-text2-xhs-img
pip install -r requirements.txt
```

流水线核心的唯一硬依赖是 Python 3.10+。图片校验环节在 Pillow 已安装时使用 Pillow，否则自动退回纯 Python 的 PNG IHDR 解析实现 — 也就是说，在**纯标准库**环境里，dry-run 和智能体模式也能照常工作。

### 3. （可选）配置 API Key

详见 `references/fallback-strategy.md`。只有你要用 `--mode api` 调 DALL·E 3 / FAL FLUX 时才需要 Key；默认降级链里的前两级（TRAE 内置 + Seedream 插件）是**完全零配置**的。

---

## 快速上手

### 花额度之前，先空跑看 Prompt

```bash
cd yy-text2-xhs-img
python scripts/generate.py ^
  --topic "20+ 夏天油皮护肤三步曲" ^
  --cards 4 ^
  --style ins-aesthetic ^
  --ratio 3:4 ^
  --dry-run-prompts
```

这条命令会把**封面 + 3 张正文**的 Prompt 和负面词完整打印出来，方便你在调用模型前先核对调色板锁死行和场景细节。新的选题强烈建议先空跑一次。

### 智能体模式（默认） — 用宿主自带的生图工具

```bash
python scripts/generate.py ^
  --topic "七夕限定国潮口红套组推荐" ^
  --cards 5 ^
  --style neo-chinese ^
  --ratio 3:4
```

它会：
1. 生成 `output/<run-id>/tasks.json`，每张卡片一个任务（Prompt、负面词、TRAE 尺寸预设、比例、宽高）。
2. 把路径打印出来；宿主依次读取任务，调用 `GenerateImage` 或 Seedream 插件，将 `cover.png`、`card_1.png`……写入运行目录。
3. 调用 `--resume <run-id>` 进行 PNG 校验 + 写 `manifest.json`。

### API 模式 — 直连 DALL·E 3 / FLUX（环境变量里有 Key 时）

```powershell
# 每个 Shell 先设置一次 Key（PowerShell 示例）：
$env:OPENAI_API_KEY = "sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
$env:FAL_KEY          = "xxxxxxxxxxxxxxxx:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# 然后生成：
python scripts/generate.py ^
  --topic "七夕限定国潮口红套组推荐" ^
  --cards 5 ^
  --style neo-chinese ^
  --ratio 3:4 ^
  --mode api ^
  --providers fal-flux,dalle3   # 只选付费供应商，跳过智能体专用的
```

失败的调用会按 2 → 4 → 8 秒退避重试 3 次；某家供应商彻底挂了就切到下一家；**每一张**图片写进 manifest 之前都必须通过 PNG 头校验和比例校验。

### 严格模式（像素级比例对齐）

默认比例容差是 1%（允许尺寸桶取整的误差）。如果你的笔记版式是硬裁切裁切框、必须严格 3:4，加上 `--strict`：

```bash
python scripts/generate.py … --strict
```

原本的软警告会升级为硬拒绝 → 重试 → 连续 3 次失败就换下一家供应商。

---

## 仓库结构

```text
yy-text2-xhs-img/
├── SKILL.md                        # Skill 清单 + 智能体执行规则
├── README.md                       # ← 你当前看的就是这份
├── LICENSE                         # MIT 许可证
├── requirements.txt                # 可选 Python 依赖
│
├── styles/
│   └── presets.json                # 8 套预设 + 负面词库 + 尺寸比例映射
│
├── scripts/
│   └── generate.py                 # 主 CLI：Schema → Prompt → 多模型分发 → 校验 → 清单
│
├── references/
│   ├── prompt-engineering.md       # Prompt 是怎么构建的、为什么这么写 + 常见故障修复
│   ├── model-matrix.md             # 模型选型对比矩阵（能力表）
│   └── fallback-strategy.md        # 降级链行为细节 + Key 配置 + resume 语义
│
├── tests/
│   └── test_generate.py            # 纯函数单测（无网络），覆盖 6 大类逻辑
│
├── evals/
│   └── evals.json                  # Prompt/尺寸/降级链 三方面的回归用例
│
└── .github/
    └── workflows/ci.yml            # Ubuntu-22.04 × Py 3.10/3.11/3.12：语法校验 + 预设结构校验 + pytest
```

---

## 本地跑测试

```bash
pip install -r requirements.txt   # 至少装 pytest；Pillow 能打开额外校验分支
pytest tests/test_generate.py -v --cov=scripts --cov-report=term
```

测试覆盖的点：

- 预设 Schema 完整性（每个字段都有，不空）
- 8 套内置预设 × 尺寸映射 × 通用负面词
- Prompt 拼接：封面 / 步骤 1 / 中间卡 / 收尾图的角色话术
- 调色板锁定行存在 + 5 种 Hex 列齐
- 负面词分层去重（基础 → 预设 → 用户 exclude）
- exclude & has_text 行为
- 主题关键词 → 场景具象化命中
- PNG Magic & 尺寸校验（含纯 Python IHDR 解析回退路径）
- 尺寸映射查询 + 1080×1440 假 PNG 的比例匹配
- 全空环境下供应商降级 → 预期 "全部失败"（不是 bug）
- 5 张卡 国潮口红 选题的 CLI dry-run JSON 往返

---

## 路线图与贡献

近期计划：
- [ ] 新增第二波适配器：`fal-ai/flux-pro` 和 Seedream 5（等官方暴露接口）。
- [ ] 集级一致性：支持 `--same-seed <N>`，用 manifest 中的种子重跑扩图。
- [ ] 第 9 套预设 `k-beauty-glow`（已有人提需求）& 品牌自定义预设子文件教程。
- [ ] 端到端：PR 级别 `--dry-run` 的 Actions 冒烟测试。

贡献流程：
1. 先开 issue 描述你修改要解决的场景（避免重复劳动，也能挡住跑偏的 PR）。
2. 对应测试加进 `tests/test_generate.py`，保证修完就不再回退。新增预设的话，在 `TestPresetSchema` 里加一段显式断言，并在 `evals/evals.json` 补一组回归用例。
3. 本地全量测试过：在**纯标准库**和**装了 Pillow** 两种环境都跑 `pytest tests/ -v`，确保纯 Python PNG 解析路径没被你弄坏。
4. 发 PR，CI 会再跑一遍矩阵。

---

## 许可证

MIT © 2026 ivercurry99。详见 `LICENSE` 文件。

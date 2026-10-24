# yy-rednote-img

把简短文本转换成小红书图文配图。风格预设、负面词和尺寸映射在调用模型前由配置文件确定，出图接口故障时按顺序切换供应商，每张图片生成后做文件完整性和比例校验。

## 项目简介

`yy-rednote-img` 接收简短文本需求（例如「夏天油皮护肤三步曲，做 4 张小红书配图」），输出 3:4 或其他常用比例的图片文件。调用出图接口前，各家供应商的尺寸映射、调色板、构图规则和风格负面词都由预设文件确定，不需要每次调用都重新编写提示词。

核心脚本 `scripts/generate.py` 处理以下几类问题：

| 问题 | 处理方式 |
|---|---|
| 同一次出图里，卡片之间的颜色和风格不一致 | 8 套风格预设（`styles/presets.json`），每套锁定 5 色调色板、构图、灯光、氛围、镜头和反风格负面词 |
| 生成结果出现水印、畸形人体、乱码文字 | 通用负面词库（30+ 条）、预设专属负面词和用户自定义负面词在每次调用时分层叠加 |
| 一个供应商故障导致整篇笔记无法完成 | 4 路供应商降级链：TRAE 内置 → Seedream 插件 → DALL·E 3 → FLUX。每家最多重试 3 次（指数退避），全部失败后切换下一家 |
| 图片比例不符合小红书首页要求 | 固定 sizeMap：3:4 / 1:1 / 4:3 / 9:16 对应各供应商最接近的原生尺寸 |
| 损坏或截断的图片被误认为生成成功 | 每张图检查 PNG 文件头、50 KB 下限和比例容差（< 1%），不合格的文件移入 `_failed/` 并重试 |
| 需要复现某一次出图 | `manifest.json` 记录每张卡片的供应商 ID、种子、Prompt、预设和尺寸，重新执行即可复现 |

## 运行模式

两种模式走同一套核心逻辑：

- 智能体模式（默认）：脚本生成 `tasks.json` 描述每张卡片；宿主（TRAE / Codex / Claude Desktop 的 skills 目录）调用自带的 `GenerateImage` 或 Seedream 插件生成图片；脚本随后校验文件并写入 manifest。
- API 模式（`--mode api`）：环境变量存在 Key 时，脚本直接调用 OpenAI DALL·E 3 或 FAL FLUX。

## Prompt 拼接与定制

每次调用模型前，脚本按固定顺序拼接 Prompt：主体还原 → 构图 → 灯光 → 氛围 → 调色板锁定 → 场景具象化 → 角色定位，然后为封面、步骤卡、过渡卡和收尾图分别拼上各自的角色话术。

在此基础上，CLI 参数可以定制每次出图：

```
--keywords "道具1, 道具2, 材质3"
--audience "20-28 岁东亚女生"
--mood "治愈、软糯、奶油马卡龙"
--exclude "不露脸、不要手"
--extra-prompt-suffix "品牌一致性规则：圆形点缀、烫金线条"
```

核心逻辑是纯函数并有单元测试覆盖；脚本内部不播种随机数，两次运行之间不存在隐藏状态。

## 风格预设

8 套内置预设，每套包含 5 色调色板、4 条以上构图规则、4 条以上灯光规则，以及氛围、镜头、质量增强和反风格负面词：

| `--style` | 视觉印象 | 最适合 |
|---|---|---|
| `ins-aesthetic` | 奶白 + 50mm 柔光窗边 + 低对比 + 留白柔和 | 护肤 · 穿搭平铺 · 生活方式 |
| `clean-minimal` | 纯白无缝 + 俯视对称 + 硬接触阴影 | 单品主图 · 美妆 · 电商画册 |
| `neo-chinese` | 朱砂红 + 24K 金 + 水墨晕染 + 国潮纹样 | 节日 · 茶饮 · 口红 · 文创 |
| `y2k-funky` | 品红/青蓝 铬金属 + 闪光灯过曝 + 珠光亮面 | Z世代 · 校园 · 潮流 · 夏日选题 |
| `magazine-editorial` | Portra 400 颗粒 + 大片 3 灯布光 + 三分法 + 30% 安全文案区 | 深度长文 · 观点笔记 · 高定穿搭 |
| `emotional-daily` | 黄金时段暖色 + 35mm 抓拍 + 胶卷重颗粒 + 生活切片 | 美食日记 · 探店 · 旅行情绪 |
| `product-flatlay` | 正 90° 平铺 + 麻布/牛皮纸背景 + 道具同色系点缀 | 合集 · 开箱 · 护肤步骤 · 拆箱 |
| `cute-illustration` | 粗边圆润描边 + 三丽鸥马卡龙色 + 扁平矢量 | 知识卡片 · 教程 · 儿童教育 |

完整 Schema 见 `styles/presets.json`；追加自定义预设的方法见 `references/prompt-engineering.md` 第 7 节。

## 安装

### 作为智能体 Skill 安装

把下面这句话发给任意支持 Skill 的智能体（TRAE、Claude Desktop、Alma、Codex…）：

```text
请从此 URL 安装 Skill：https://github.com/ivercurry99/yy-rednote-img
```

如果你本机有 `skills` CLI：

```bash
npx skills add ivercurry99/yy-rednote-img
```

也可以手动克隆到你的技能目录：

```bash
# 常见宿主目录，根据你自己的软件改：
#   TRAE:       ~/.trae/skills/   (Windows: %USERPROFILE%\.trae\skills\)
#   Claude:     ~/.claude/skills/
#   Alma:       ~/.config/Alma/skills/
git clone https://github.com/ivercurry99/yy-rednote-img.git <your-skills-dir>/yy-rednote-img
```

### 安装 Python 依赖（仅 `--mode api` 需要）

```bash
cd yy-rednote-img
pip install -r requirements.txt
```

流水线核心的唯一硬依赖是 Python 3.10+。图片校验环节在 Pillow 已安装时使用 Pillow，否则退回纯 Python 的 PNG IHDR 解析；纯标准库环境下，dry-run 和智能体模式可以照常工作。

### 配置 API Key（可选）

详见 `references/fallback-strategy.md`。只有用 `--mode api` 调 DALL·E 3 / FAL FLUX 时才需要 Key；默认降级链的前两级（TRAE 内置 + Seedream 插件）不需要任何配置。

## 快速上手

### 先空跑查看 Prompt

调用模型前，可以先用 `--dry-run-prompts` 打印完整的 Prompt 和负面词，确认调色板锁定行和场景细节后再实际生成。新的选题建议先空跑一次：

```bash
cd yy-rednote-img
python scripts/generate.py ^
  --topic "20+ 夏天油皮护肤三步曲" ^
  --cards 4 ^
  --style ins-aesthetic ^
  --ratio 3:4 ^
  --dry-run-prompts
```

### 智能体模式（默认）

```bash
python scripts/generate.py ^
  --topic "七夕限定国潮口红套组推荐" ^
  --cards 5 ^
  --style neo-chinese ^
  --ratio 3:4
```

执行过程：

1. 生成 `output/<run-id>/tasks.json`，每张卡片一个任务（Prompt、负面词、TRAE 尺寸预设、比例、宽高）。
2. 打印路径；宿主依次读取任务，调用 `GenerateImage` 或 Seedream 插件，将 `cover.png`、`card_1.png` 等写入运行目录。
3. 调用 `--resume <run-id>` 校验 PNG 文件并写 `manifest.json`。

### API 模式

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

失败的调用按 2 → 4 → 8 秒退避重试 3 次；某家供应商连续失败后切换下一家；每张图片写入 manifest 前都要通过 PNG 头校验和比例校验。

### 严格模式

默认比例容差是 1%，允许尺寸桶取整的误差。如果笔记版式要求严格的 3:4，加 `--strict` 把软警告升级为硬拒绝，连续 3 次失败后切换供应商：

```bash
python scripts/generate.py … --strict
```

## 仓库结构

```text
yy-rednote-img/
├── SKILL.md                        # Skill 清单 + 智能体执行规则
├── README.md
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
│   └── test_generate.py            # 纯函数单测（无网络）
│
├── evals/
│   └── evals.json                  # Prompt/尺寸/降级链 三方面的回归用例
│
└── .github/
    └── workflows/ci.yml            # Ubuntu-22.04 × Py 3.10/3.11/3.12：语法校验 + 预设结构校验 + pytest
```

## 测试

```bash
pip install -r requirements.txt   # 至少需要 pytest；Pillow 能打开额外校验分支
pytest tests/test_generate.py -v --cov=scripts --cov-report=term
```

测试覆盖以下内容：

- 预设 Schema 完整性（每个字段都有，不空）
- 8 套内置预设 × 尺寸映射 × 通用负面词
- Prompt 拼接：封面 / 步骤 1 / 中间卡 / 收尾图的角色话术
- 调色板锁定行存在 + 5 种 Hex 列齐
- 负面词分层去重（基础 → 预设 → 用户 exclude）
- exclude & has_text 行为
- 主题关键词 → 场景具象化命中
- PNG Magic & 尺寸校验（含纯 Python IHDR 解析回退路径）
- 尺寸映射查询 + 1080×1440 假 PNG 的比例匹配
- 全空环境下供应商降级 → 预期「全部失败」（不是 bug）
- 5 张卡国潮口红选题的 CLI dry-run JSON 往返

## 参与贡献

近期计划：

- [ ] 新增适配器 `fal-ai/flux-pro` 和 Seedream 5（等待官方暴露接口）。
- [ ] 支持 `--same-seed <N>`，用 manifest 中的种子重跑并扩图。
- [ ] 新增第 9 套预设 `k-beauty-glow`，以及品牌自定义预设子文件的教程。
- [ ] 在 Actions 中加入 PR 级别的 `--dry-run` 冒烟测试。

贡献流程：

1. 先开 issue 描述修改要解决的场景，避免重复劳动。
2. 对应测试加进 `tests/test_generate.py`，保证修完不回退。新增预设时，在 `TestPresetSchema` 里加显式断言，并在 `evals/evals.json` 补一组回归用例。
3. 在纯标准库和安装了 Pillow 的两种环境里分别运行 `pytest tests/ -v`，确认纯 Python PNG 解析路径正常。
4. 发 PR，CI 会再运行一遍测试矩阵。

## 许可证

MIT © 2026 ivercurry99。详见 `LICENSE` 文件。

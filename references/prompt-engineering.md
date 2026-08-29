# 小红书 Prompt 工程手册

本技能的第一目标是**稳定**：每一次生成都要落在用户预期的平台审美范围内，
而不是"摇骰子开盲盒"。`scripts/generate.py` 里的 Prompt 拼接顺序是严格写死的——
本手册会解释**为什么**每一块都要按这个顺序放，以及你想做扩展时该怎么改，
才不会破坏一致性。

---

## 1. 固化的 Prompt 拼接公式

**所有 Prompt 都严格按照以下顺序**构建（参见 `build_prompt_for_card`）：

```
[qualityBooster]        → 先告诉模型：画质下限是什么
[composition rules]     → 先定构图和取景，再谈颜色和灯光（摄影的顺序）
[lighting rules]        → 先布光，再谈氛围（摄影棚逻辑）
[atmosphere words]
[camera lens]
[PALETTE LOCK 锁定行]   → 列出 5 个 Hex + 写上 "strictly"，专门对抗颜色漂移
[topic visualised]      → 由主题关键词展开的**具体场景**，不是抽象词
[keywords]              → 道具 / 材质 / 具体物体
[audience bias]         → 目标人群，影响肤色、穿搭、年龄
[mood adjectives]
[CARD ROLE 角色话术]    → 封面 / 步骤一 / 收尾结果图，影响巨大
[text handling]         → 默认 "no text…"，除了 dalle3 其他模型写中文全是乱码
[platform tagline]      → "xiaohongshu style, pinterest aesthetic, viral social media hero visual"
[extra suffix]          → 用户注入的品牌一致性 Hook
```

**为什么这个顺序不能乱？**
扩散模型对 Prompt 开头的权重明显高于结尾（语义越靠尾巴越衰减），
所以画质规则、构图规则必须放在装饰元素**之前**。反过来，如果你先写场景，
镜头和构图规则会被模型忽略，构图直接飘。

---

## 2. 主题 → 具象场景

**禁止写抽象 Prompt。** 脚本内置了一张主题关键词 → 具象视觉句子的映射
（在 `scripts/generate.py` 里的 `_TOPIC_VISUAL_KEYS`）：

| 抽象主题 | ❌ 错误写法（画不出来） | ✅ 正确写法（模型能画） |
|---|---|---|
| "护肤三步" | "skin care steps" ❌ | 奶油大理石台面，玻璃化妆品瓶， toner 棉片，滴管滴着精华，面霜罐，手指拍脸颊 |
| "穿搭灵感" | "fashion outfits" ❌ | 精心挑选的服装平铺：奶白西装、真丝衬衫、乐福鞋、迷你手提包、手表，置于暖米色麻布上 |
| "英语学习计划" | "english learning" ❌ | 淡黄色摊开的笔记本手写词汇、Apple Pencil、复古牛津词典、抹茶拿铁、木质桌面 |
| "数码开箱" | "new phone" ❌ | 磨砂黑色桌面、新手机、耳机壳、Type-C 线、卡盒、柔和环形主光 |

往 `_TOPIC_VISUAL_KEYS` 里新增关键词时，遵循 4 条规则：
1. **只选一个镜头角度**（平铺 / 特写 / 主图 / 过肩），固定住不要混。
2. 至少写 **3 件具体物体**。
3. 写出它放在**什么表面**上（大理石、麻布、牛皮纸、木桌、梳妆台）。
4. 句子控制在 60 词以内 — 太长会把前面的构图规则"稀释掉"。

---

## 3. 调色板锁定机制

每条 Prompt 中间都有这样一行：

```
PALETTE LOCK strictly use these 5 colors in hex: #FFF8F0, #F5E6D3, #E8D5C4, #D4B896, #A67B5B — do not introduce any other color or neon hue
```

这行是从 `presets.json` 中 `palette: []` 和 `paletteLock: true` 自动生成的。
实测它在 FLUX / Seedream / DALL·E 3 三家上都能显著降低颜色偏出范围的概率。

**常见故障：**
- ❌ 写了 `monochrome / black and white` — 会压制调色板，直接变成灰图。
- ❌ `y2k-funky` 预设里写了"pastel" — 与预设的高饱和矛盾。
- ✅ 新增预设时，调色板 5 色必须覆盖：主背景色、主色、次色、点缀色、深对比色（5 个桶各一种）。

---

## 4. 卡片角色话术（CARD ROLE）

同一条选题，封面和正文卡的构图目标**完全不同**。脚本给 4 种内置角色各自写了专用
Hook 模板：

| 角色 | 策略 | Hook 核心 |
|---|---|---|
| 封面 `cover` | 3 秒抓眼球，必须有"停划点" | 居中构图 + 标题暗示区（copy-safe 20% 顶部）+ "viral hero cover" 话术 |
| 步骤一 `card_1` | 解释"这篇在讲什么" | 场景化"before / action 1"示意 + "Step 1 清晰可读占位" |
| 中间卡 `card_2..N-1` | 递进，带下一步暗示 | 动作中的特写 + 信息密度均匀分布 + 过渡感 |
| 收尾卡 `final` | 展示结果图，勾互动 | Before/After 对比 or 最终效果特写 + "Save this, follow for more" 平台话术 |

你可以在 `build_prompt_for_card` 的 `card_role` 分支里新增自定义角色。
注意：角色话术写在**靠后**的位置 — 它们负责"情绪和方向"，不能盖过前面的构图规则。

---

## 5. 负面词三层叠加

负面词不是越长越好，而是三层相加再**去重**：

1. **`negativeBase` 通用负面词库**（30+ 条）：水印、畸形、过曝、HDR、
   六指、JPEG 伪影、低分辨率、压缩痕迹…… 任何小红书图都不该出现的东西。
2. **`negativeExtra` 预设专属反风格词**：比如 `ins-aesthetic` 反"vivid / saturated / harsh / hdr / overexposed / cartoon render"，防止奶白风被艳色冲掉。
3. **`--exclude` 用户自定义**：例如不露脸、不要模特、不要手……

重复词合并后按长度稳定排序再输出，避免每次 Prompt 里顺序不同导致结果微抖。

---

## 6. 文字处理（has_text 开关）

默认：

```
no text, no watermark, no captions, no letters, no logo
```

因为除了 DALL·E 3，其它模型画中文字基本都是乱码或畸形字。
如果用户确实要画面里有中文字（比如产品包装 slogan）：
1. `has_text=True`；
2. 脚本**把 dalle3 提升为降级链第一选择**（如果在链里）；
3. 平台话术改为"清晰印刷字体、对齐规范的中文排版"。

DALL·E 3 的中文仍不够完美，建议 Post 时把重要文案改成后期叠字，不要依赖生图。

---

## 7. 如何追加自定义预设

`styles/presets.json → "presets"` 对象中按下面 Schema 填新条目即可，
字段一个都不能少，否则 `TestPresetSchema` 会挂：

```jsonc
// inside styles/presets.json → "presets" object
"your-new-preset": {
  "displayName": "好读中文名，不超过 24 字",
  "palette":    ["#背景色", "#主色", "#次色", "#点缀色", "#深对比色"],
  "paletteLock": true,
  "composition": ["4 条以上构图规则，每条是具体可执行指令"],
  "lighting":    ["4 条以上布光规则，顺序：光源位置→阴影→色温"],
  "atmosphere":  ["3-5 条氛围形容词，和 palette 保持一致"],
  "camera":      "一条完整镜头话术（焦段、光圈、景深）",
  "qualityBooster": ["5 条画质增强词，不重复 base 中的"],
  "negativeExtra": ["3-8 条反风格负面词，和其他预设不重叠"],
  "bestFor":     ["适用场景 1", "场景 2", "场景 3"]
}
```

改完跑一次：

```bash
pytest tests/test_generate.py::TestPresetSchema -v
```

全部通过，才算合法预设。

---

## 8. 常见故障排查（FAQ）

| 症状 | 最可能原因 | 修复方式 |
|---|---|---|
| 两次出图颜色像两个世界 | ① paletteLock=false 或 Hex 写重；② 负面词里有 black and white；③ 模型选了 dalle3（调色板稳定性 3/5），换 fal-flux 或 seedream-plugin。 | 打开 `--dry-run-prompts` 看 PALETTE LOCK 行；改 provider 顺序。 |
| 总是有手畸形 / 六指 | FLUX 以外的模型常见（手指真实感 3-4/5）。 | 换 fal-flux；或在 exclude 里加 "no hands, no fingers, cropped wrist" 让模型主动裁掉手。 |
| 图里有中文乱码字 | 除 dalle3 外所有模型默认都会出。 | `has_text=False`（默认），文案后期叠。 |
| 3:4 比例的图总被裁出主角 | ① sizeMap 被改，不匹配模型原生桶；② composition 里写了"wide angle"。 | 对照 `references/model-matrix.md §2` 恢复 sizeMap；删 wide angle。 |
| 同一 set 里 4 张图像 4 种风格 | ① `--same-seed` 没开；② provider 在中间切换了（seedream → dalle3 风格跳变最大）。 | 开 `--same-seed`；或显式 `--providers fal-flux` 钉死一家。 |
| 生成图片小于 50KB 被判定无效 | 网络截断或 API 返回占位缩略图。 | manifest.failures 里会记原因；默认重试 3 次，一般下一轮就好。 |

最后一条铁律：**改 Prompt 顺序前，先写一个能复现故障的 pytest 用例，再改。**
否则你的"优化"很可能悄悄破坏另一个选题的稳定性。

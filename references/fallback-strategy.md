# 降级链设计 & API Key 管理

整个流水线**不会**因为某一家供应商挂了就彻底崩。
`scripts/generate.py` 中 `run_provider_chain()` 的循环是**唯一一处**做供应商决策的地方 —
本文档把它的行为拆解清楚，同时说明 secrets 该怎么安全配置。

---

## 1. 默认降级顺序

```
1. trae-native       （宿主有 GenerateImage 工具就用，零配置）
      ↓
2. seedream-plugin   （TRAE Seedream 插件已授权就用）
      ↓
3. dalle3            （环境变量里有 OPENAI_API_KEY 就用）
      ↓
4. fal-flux          （环境变量里有 FAL_KEY 就用）
      ↓
致命：全部失败 — 打印结构化失败日志 + 退出码 1。
```

用 CLI 参数可以重写这条链：

```bash
# 省钱模式：只走免费两家
python scripts/generate.py --providers trae-native,seedream-plugin …

# 品牌发稿模式：只走付费两家
python scripts/generate.py --providers fal-flux,dalle3 …
```

如果 `has_text=true`（画面里要清晰中文字），脚本会自动：
1. 如果 dalle3 在链里但不在首位 → 把 dalle3 提到最前面；
2. 如果 dalle3 根本不在链里 → 在 stderr 打印一条黄字警告提醒你。

---

## 2. 什么时候切换到下一家？

每家供应商的尝试循环内，有**两种严重级别**的失败：

| 严重程度 | 触发条件 | 行为 |
|---|---|---|
| **立刻跳过（不重试）** | 工具不存在 / 缺 Key / 401 鉴权失败 / 403 权限不足 / 429 限流且没有 `reset-time` 头。 | 把跳过原因写入 `manifest.failures`，进入下一家供应商。 |
| **可重试（每家最多 3 次）** | `5xx` / 网络超时 / 200 OK 但 PNG 头损坏 / 文件 < 50KB / 比例不对（严格模式）。 | 指数退避：2s → 4s → 8s 等待。连续 3 次失败后换下一家供应商。 |

### 为什么不无限重试？

因为现实里任何一家供应商挂，持续时间基本都是**小时级**。
如果用户每张图等 10+ 秒 × 3 次重试 × 4 家供应商，已经是好几分钟。
脚本必须在最后给出一份可读的结构化报告，例如：

> "seedream-plugin 返回 429（额度用尽），第 1 次尝试后直接跳过；
> dalle3 尝试 3 次全是 503；fal-flux 在第 1 次尝试成功，耗时 2300 ms。"

这份报告写入 `manifest.json → cards[i].result_reason`，用户看到就能立刻知道：
"哦，该给 Seedream 充额度了 / 该给 FAL 提限流了"，而不是傻等。

---

## 3. Secrets 配置

### 3.1 最低原则

- ❌ 绝不把 Key 写进代码、仓库、README。
- ❌ 绝不把 Key 打印进 stdout / 日志 / 测试快照。
- ✅ 只从环境变量读取，读取失败就**静默降级**到下一家，不报错。
- ✅ CI 环境里（GitHub Actions）用 `Repository secrets` 注入，
  pytest 里读不到也没关系，相关断言走的是 "all providers failed expected" 分支。

### 3.2 需要的环境变量清单

| 供应商 | 环境变量名 | 在哪里申请 |
|---|---|---|
| DALL·E 3 | `OPENAI_API_KEY` | https://platform.openai.com/api-keys → Project API Key |
| FLUX Dev (FAL) | `FAL_KEY` | https://fal.ai/dashboard/keys → 新建 Key，格式 `id:secret` |
| TRAE 内置 `GenerateImage` | — | 宿主代理，不需要本地配置。 |
| Seedream 插件 | — | 插件授权流程走 TRAE 宿主，不需要本地 Key。 |

### 3.3 各操作系统设置方式

**PowerShell（Windows，当前 Shell 生效）：**
```powershell
$env:OPENAI_API_KEY = "sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
$env:FAL_KEY          = "xxxxxxxxxxxxxxxx:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

**cmd（Windows）：**
```bat
set OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
set FAL_KEY=xxxxxxxxxxxxxxxx:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**bash / zsh（macOS / Linux）：**
```bash
export OPENAI_API_KEY="sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export FAL_KEY="xxxxxxxxxxxxxxxx:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

**持久化：** 写入 `$PROFILE`（PowerShell）、`.bashrc` / `.zshrc`（Unix），
或用 1Password / Bitwarden 的 env-cli 注入，不建议把 Key 明文贴进这些文件。

---

## 4. Resume 语义（断点续跑）

跑批失败后，可以用 `--resume <run-id>` 续跑：

```bash
# 上次生成到一半卡在了 fal-flux 503
python scripts/generate.py \
  --topic "七夕限定国潮口红套组推荐" \
  --cards 5 \
  --style neo-chinese \
  --ratio 3:4 \
  --resume 20260829-201533-a1b2c3
```

Resume 的行为：
1. 读取 `output/<run-id>/manifest.json`；
2. 对于每张卡片：
   - 如果已有 `final_path` 且通过 `validate_png + validate_ratio` → 跳过；
   - 如果记录为 `_failed/xxx.png` → 重新跑完整降级链；
3. 最终重新写一份 manifest。

> Resume 不会"记忆上次哪家挂了"，因为上次是 429 可能这秒已经释放。
> 你可以通过 `--providers` 显式排除上次挂的那家。

---

## 5. 失败日志结构

`manifest.json` 里每张卡片的 `failures` 字段是一个数组，形如：

```json
{
  "failures": [
    { "provider": "seedream-plugin", "severity": "skip", "reason": "plugin_not_authorized", "at_ms": 210 },
    { "provider": "dalle3", "severity": "retry",  "reason": "png_magic_mismatch",    "at_ms": 18020, "attempt": 1 },
    { "provider": "dalle3", "severity": "retry",  "reason": "png_magic_mismatch",    "at_ms": 22041, "attempt": 2 },
    { "provider": "dalle3", "severity": "retry",  "reason": "png_magic_mismatch",    "at_ms": 30088, "attempt": 3 },
    { "provider": "fal-flux", "severity": "ok",   "reason": "success",               "at_ms": 2301,  "attempt": 1 }
  ],
  "provider_id": "fal-flux",
  "result_reason": "success via fal-flux after 3 dalle3 retries + seedream skipped (not authorized)"
}
```

字段说明：
- `severity`：`skip` / `retry` / `ok`，立刻跳过 / 重试 / 成功。
- `reason`：枚举字串，方便 grep（例如 `missing_tool` / `401` / `429_no_reset` /
  `5xx` / `timeout` / `png_magic_mismatch` / `too_small` / `bad_ratio`）。
- `at_ms`：这次尝试耗时（毫秒）。
- `attempt`：同一家供应商的第几次尝试。

排障时先搜 `reason` 的枚举值，基本能 10 秒定位问题在哪一层。

---

## 6. 安全审计清单

每次升级 `generate.py`、或新增供应商适配器时，过一遍：

- [ ] 供应商 ID 只从 `--providers` 白名单解析，不接受任意字串当 ID。
- [ ] 读 Key 时用 `os.getenv()`，读不到返回 None，**不要抛 KeyError**。
- [ ] 任何日志 / manifest / stderr 里，Key 的打印必须脱敏
      （写 `sk-proj-abcd…` 而非完整 Key，或干脆不写）。
- [ ] 重试退避必须有最大上限（当前 8 s），防止"429 无限重试轰炸"。
- [ ] `RequestAuthorization` 宿主必须在用户主动要求配置外部服务时才调用。

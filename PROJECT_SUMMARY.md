# 万能视频下载 · 项目总结

> 立项 → MVP → 稳定可用：一个 yt-dlp + FastAPI 的极简视频下载站，
> 前端复刻 baidu.com 的"一框一按钮"体验，后端覆盖 1000+ 平台。

---

## 一、项目概览

| 项 | 内容 |
| --- | --- |
| 项目名 | 万能视频下载（Universal Video Downloader） |
| 目标 | 粘贴链接 → 解析 → 一键下载，零注册、零数据库、单进程部署 |
| 技术栈 | Python 3.10+ / FastAPI / yt-dlp / 原生 HTML + CSS + JS |
| 部署形态 | `python run.py` 单命令启动，默认 `0.0.0.0:8000` |
| 平台覆盖 | YouTube / B站 / 抖音 / 快手 / 小红书 / TikTok / Twitter / Instagram + 1000+ |
| 商业模型 | 免费基础下载 + VIP 增值（4K/8K、AI 总结、字幕翻译、无限批量） |

---

## 二、最终能力清单

### 已交付（Free）
- 单视频解析：标题、封面、时长、作者、来源平台、可用清晰度/格式列表
- 单视频下载：自动选择最优策略（详见第三节）
- 批量解析：单次最多 3 条（免费额度），服务端强制限制
- 多端适配：PC、手机浏览器自适应
- 智能 Cookies 注入：浏览器自动 + 手动 `cookies/<site>.txt` 双通道
- 友好错误提示：将 yt-dlp 原生英文报错翻译成可执行的中文操作指南
- 临时文件自动清理：每 10 分钟扫描，TTL 1 小时

### VIP 引导（演示性质，未接入支付）
- 4K / 8K 原画清晰度
- AI 视频内容总结
- 字幕翻译（50+ 语言）
- 无限批量下载
- 顶部 + 卡片 + 弹窗 三层引导

---

## 三、核心设计：混合下载策略

这是本项目最重要的一个设计决策，直接决定服务器成本和用户体验。

```
┌────────── 浏览器 ──────────┐         ┌────────── 服务器 ──────────┐
│  /api/parse  ──► yt-dlp 解析元数据 + 全量格式 (含直链 url)       │
│                                                                  │
│  策略 1：直链下载（零服务器流量）                                │
│    条件：has_video && has_audio && !needs_merge && url 可用      │
│    动作：<a href="直链" download> 由浏览器直接拉                 │
│                                                                  │
│  策略 2：服务器代理（合并 / 防盗链兜底）                         │
│    条件：needs_merge 或 直链 403 / Referer 限制                  │
│    动作：POST /api/download → yt-dlp 拉到 tmp/<uuid>/            │
│            ─► GET /api/file/{uuid} 流式下发 ─► 下载完即删        │
└──────────────────────────────────────────────────────────────────┘
```

**收益**：YouTube 1080p+ 这种音视频分离的场景走代理；抖音 / B 站普通清晰度走直链。
对 1 万次下载，估算可以把服务器出口流量降低 70%+。

---

## 四、目录结构

```
free-video-downloader/
├── run.py                     # 单命令入口
├── requirements.txt           # 5 个依赖，无数据库无中间件
├── README.md                  # 用户视角说明
├── PROJECT_SUMMARY.md         # 本文件
├── .gitignore                 # 排除 tmp/、cookies/*.txt、venv 等
│
├── backend/
│   ├── main.py                # FastAPI 入口 + lifespan 后台清理任务
│   ├── config.py              # 路径、TTL、批量上限、VIP 阈值
│   ├── utils.py               # ffmpeg 探测 / 浏览器 cookies / URL 规范化
│   ├── api/routes.py          # /api/parse · /api/download · /api/batch · /api/file
│   └── services/
│       ├── extractor.py       # yt-dlp 解析封装 + 格式归一化 + 去重排序
│       └── downloader.py      # 服务器代理下载 + 临时文件管理 + 周期清理
│
├── frontend/                  # 由 FastAPI StaticFiles 直接挂载在 /
│   ├── index.html             # 单视频下载页
│   ├── batch.html             # 批量下载页
│   ├── favicon.svg
│   ├── css/style.css          # 百度极简风 + VIP 金色渐变
│   └── js/
│       ├── main.js            # 单视频页面逻辑
│       └── batch.js           # 批量页面逻辑
│
├── cookies/                   # 手动 cookies 目录（.txt 已 ignore）
│   └── README.md              # 抖音/B站 等高风控站点的 cookies 导入指南
│
└── tmp/                       # 运行时临时目录，启动自动创建
```

---

## 五、关键模块速览

### 5.1 `backend/services/extractor.py` — 解析
- `extract_info(url)`：yt-dlp 调用 + 容错重试（cookies 解密失败时降级）
- `_build_format` / `_dedupe_formats` / `_sort_formats`：把 yt-dlp 几十条 raw 格式压缩为前端可消费的清晰列表
- 返回带 `is_vip`（≥2160p）/ `needs_merge`（无音轨）/ `filesize_human` 等业务字段

### 5.2 `backend/services/downloader.py` — 代理下载
- `download_to_tmp(url, format_id, needs_merge)`：每个任务一个 uuid 子目录，互不干扰
- 失败时同样有 cookies 降级重试
- `cleanup_stale_jobs` / `periodic_cleanup`：lifespan 启动 + 每 10 min 扫一次

### 5.3 `backend/utils.py` — 平台兼容性"脏活"集中地
本文件解决了实战中最容易踩坑的几类问题：
- **URL 规范化**：抖音 `?modal_id=` / B 站 BV 号截取，让 yt-dlp 识别得了
- **ffmpeg 探测**：PATH + `FFMPEG_HOME/PATH/BIN` 环境变量 + 常见目录
- **Cookies 注入**：手动 `cookies/<site>.txt` 优先于浏览器 cookies；
  Windows 上 Chrome/Edge 127+ 因 App-Bound Encryption 无法解密，自动跳过浏览器 cookies
- **错误兜底识别**：`is_cookie_decrypt_error` 识别 DPAPI 类错误，触发自动降级重试

### 5.4 `backend/api/routes.py` — 错误友好化
- `_friendly_error`：把 yt-dlp 原始报错翻译为中文 + 给出操作步骤（导出 cookies.txt 4 步法）
- ffmpeg 缺失场景：返回明确的「请选择不带"需合并"标记的格式」

### 5.5 `frontend/js/main.js` — 单视频页
- 自动剪贴板读取（聚焦输入框时尝试 `navigator.clipboard.readText`）
- VIP 触发集中管理：`data-vip="ai|subtitle|format|batch"` 属性驱动
- 三层下载状态文案：「准备下载...」→「音视频合并中...」→「传输中...」

### 5.6 `frontend/js/batch.js` — 批量页
- 实时统计已输入条数，超 3 条立即给出红字提示
- 服务端兜底（双重校验）

---

## 六、API 一览

| 方法 | 路径 | 入参 | 出参 | 说明 |
| --- | --- | --- | --- | --- |
| POST | `/api/parse` | `{ url }` | `{ ok, data: { title, thumbnail, duration, formats[…], server_has_ffmpeg } }` | 解析元数据 |
| POST | `/api/download` | `{ url, format_id, needs_merge }` | `{ ok, file_id, filename, size }` | 服务器代理下载 |
| GET  | `/api/file/{file_id}` | — | `StreamingResponse` | 流式下发，结束自动清理 |
| POST | `/api/batch` | `{ urls: string[] }` | `{ results[], free_limit, over_limit, vip_required_count }` | 批量解析（限 3） |

---

## 七、踩坑与解决方案

| # | 问题 | 现象 | 解决 |
| --- | --- | --- | --- |
| 1 | YouTube 1080p+ 无声音 | 浏览器直链下载只有视频流 | 增加 `needs_merge` 标记，强制走服务器代理 + ffmpeg 合并 |
| 2 | 抖音解析失败 | 必须带 cookies；用户输入的链接还可能是用户主页 + `?modal_id=` | `utils.normalize_url` 改写 URL；自动 / 手动 cookies 双通道 |
| 3 | Windows Chrome 127+ 无法读 cookies | DPAPI App-Bound Encryption | 检测到该类错误后剥离 `cookiesfrombrowser` 重试；引导用户用 cookies.txt |
| 4 | B 站 URL 带一堆 tracking 参数 | yt-dlp 偶发不认 | 正则提取 BV / av 号重组规范 URL |
| 5 | ffmpeg 不在 PATH | 合并失败、用户一头雾水 | 探测 `FFMPEG_HOME/PATH/BIN`；前端展示 banner + 把"需合并"格式按钮 disable 并加 tooltip |
| 6 | yt-dlp 报错全是英文 | 用户看不懂 | `_friendly_error` 翻译 + 给操作步骤 |
| 7 | 临时文件越积越多 | 磁盘炸 | lifespan 启动清一次 + 后台每 10 min 扫一次 + 下载完即删 |
| 8 | 中文文件名下载乱码 | 浏览器拿到 `?` | `Content-Disposition: attachment; filename*=UTF-8''<urlencoded>` |

---

## 八、安全 / 法务边界

- `cookies/*.txt` 默认在 `.gitignore`，避免凭据外泄
- `tmp/` 默认 `.gitignore`
- README 与页脚均明确「仅供学习交流，请勿用于商业用途」
- VIP 弹窗、支付按钮均为前端引导，**未接入真实支付通道**，避免在演示阶段产生合规风险

---

## 九、本地运行

```bash
# Python 3.10+
pip install -r requirements.txt

# 可选：安装 ffmpeg（YouTube 1080p+ / 4K 等场景需要）
# Windows: https://www.gyan.dev/ffmpeg/builds/
# macOS:   brew install ffmpeg
# Linux:   sudo apt install ffmpeg

python run.py
# → http://localhost:8000
```

需要抖音 / 小红书 / 私密 B 站视频？参考 `cookies/README.md` 导出 cookies.txt 即可。

---

## 十、后续可演进方向

### 短期
- [ ] 接入真实支付（微信 / 支付宝 H5 + 异步回调）
- [ ] 用户体系（手机号 / 微信扫码登录，最小化设计仍可不上数据库 → JWT + Redis）
- [ ] 下载进度推送（SSE 或 WebSocket，目前是按钮文案模拟）
- [ ] 失败率 / 平台分布的简易监控（接入 Prometheus 或埋点到日志）

### 中期
- [ ] AI 视频总结：抽帧 / 字幕 → LLM 接入（GPT-4 / 通义千问 / Kimi）
- [ ] 字幕翻译：whisper.cpp 转写 + 翻译模型
- [ ] 异步任务队列：Celery / RQ，把批量解析与下载从同步阻塞改为后台任务

### 长期
- [ ] 多节点部署 + S3 临时存储，前端走预签名 URL 直接下
- [ ] 浏览器扩展（一键解析当前页）
- [ ] 客户端版（Tauri 包壳，绕开服务器带宽成本）

---

## 十一、版本里程碑

| 日期 | 里程碑 |
| --- | --- |
| 2026-05-12 | 项目立项，后端骨架 + 前端首页雏形 |
| 2026-05-13 | 抖音 / B 站 cookies 通路打通；批量页 + 错误提示翻译 |
| 2026-05-14 | URL 规范化、ffmpeg 自动探测、临时文件清理稳定，**视频下载核心功能 Done** |

---

*文档维护人：项目作者。如有疑问，先看 `README.md` 与 `cookies/README.md`。*

# 万能视频下载 (Universal Video Downloader)

基于 [yt-dlp](https://github.com/yt-dlp/yt-dlp) + FastAPI 打造的万能视频下载网站，前端复刻 baidu.com 极简风，支持 YouTube / B站 / 抖音 / Twitter 等数百个平台。

> 本项目仅供学习交流，请尊重版权与平台规则。

## 特性

- **极简交互**：粘贴链接 → 解析 → 一键下载，对标 baidu.com 的简洁体验
- **覆盖全网**：依托 yt-dlp，原生支持 1000+ 视频平台
- **混合下载策略**：直链优先（零服务器带宽消耗）+ 服务器代理兜底（合并音视频流 / 防盗链场景）
- **零数据库**：纯文件 + 临时目录，单进程部署
- **多端适配**：PC / 手机浏览器均可使用
- **VIP 引导**：4K / 8K 清晰度、视频总结、字幕翻译、批量下载等 VIP 入口（演示性质）

## 快速开始

### 环境要求

- Python 3.10+
- ffmpeg（仅在需要合并音视频流时必须，推荐安装）

### 安装 & 启动

```bash
pip install -r requirements.txt
python run.py
```

浏览器访问 http://localhost:8000

## 目录结构

```
free-video-downloader/
├── requirements.txt
├── run.py
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置项
│   ├── services/
│   │   ├── extractor.py     # yt-dlp 解析封装
│   │   └── downloader.py    # 服务器代理下载
│   └── api/
│       └── routes.py        # API 路由
└── frontend/
    ├── index.html           # 单视频下载页
    ├── batch.html           # 批量下载页
    ├── css/style.css
    └── js/
        ├── main.js
        └── batch.js
```

## API

- `POST /api/parse` — 解析视频元数据 + 格式列表
- `POST /api/download` — 服务器代理下载，返回 file_id
- `GET  /api/file/{file_id}` — 流式下载文件，下载完自动清理
- `POST /api/batch` — 批量解析（免费版限 3 条）

## 法律声明

本项目为开源学习项目，使用者需自行承担因下载、传播内容产生的全部责任，作者不对任何滥用行为负责。请尊重原创、遵守平台条款。

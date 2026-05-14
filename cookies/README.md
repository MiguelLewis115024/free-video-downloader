# Cookies 目录使用指南

某些站点（抖音、TikTok、小红书、B 站、Instagram 等）对未登录请求有风控，必须带上浏览器 cookies 才能解析。本项目优先级如下：

1. 环境变量 `COOKIES_FILE` 指向的文件（绝对路径）
2. 本目录下 `<站点>.txt`，如 `douyin.txt`、`bilibili.txt`、`xiaohongshu.txt`
3. 本目录下 `cookies.txt`（通用）
4. 项目根目录 `cookies.txt`（兼容旧用法）
5. 自动从本机 Edge/Chrome/Firefox 读取（**Windows 上 Chrome/Edge 127+ 因 DPAPI 加密通常会失败**，因此推荐用上面的文件方式）

## 导出步骤（推荐）

1. 在 Edge / Chrome 应用商店搜索安装扩展 **"Get cookies.txt LOCALLY"**（开源，无外发请求）
2. 打开目标站点首页，例如 <https://www.douyin.com>，并滑动 3~5 条视频，让网站下发风控字段（如 `ttwid`、`__ac_nonce`）
3. 点击扩展图标 → **Export**（确保格式选 "Netscape"）→ 保存
4. 把保存的 `.txt` 文件按站点重命名后放到本目录：
   - 抖音 → `cookies/douyin.txt`
   - B 站 → `cookies/bilibili.txt`
   - 小红书 → `cookies/xiaohongshu.txt`
   - 其它 / 共享 → `cookies/cookies.txt`
5. 回到下载页面重试即可，**无需重启服务**

## 站点对应表

| 域名 | 文件名 |
| --- | --- |
| douyin.com / iesdouyin.com | `douyin.txt` |
| tiktok.com | `tiktok.txt` |
| bilibili.com | `bilibili.txt` |
| xiaohongshu.com / xhslink.com | `xiaohongshu.txt` |
| instagram.com | `instagram.txt` |
| twitter.com / x.com | `twitter.txt` |
| youtube.com / youtu.be | `youtube.txt` |

## 安全提示

- `cookies/*.txt` 已通过 `.gitignore` 默认排除，不会被提交到 git。如果你 fork 本项目，记得检查 `.gitignore`。
- cookies 等同临时密码，**请勿分享**。如需删除，直接删文件即可。
- 抖音的 cookies 寿命较短（通常几小时～1 天），过期后重新导出。

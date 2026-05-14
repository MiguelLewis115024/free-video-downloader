/**
 * Universal Video Downloader - main page logic.
 * - Parse video metadata via /api/parse
 * - Hybrid download: direct URL → fallback to server proxy /api/download
 * - VIP modal triggers (4K/8K, AI summary, subtitle translate)
 */

const $ = (sel) => document.querySelector(sel);

const state = {
  currentInfo: null,
  currentUrl: "",
  busyFormatId: null,
};

const VIP_REASONS = {
  ai: "AI 视频内容总结为 VIP 专享功能",
  subtitle: "字幕翻译为 VIP 专享功能",
  format: "4K / 8K 原画下载为 VIP 专享",
  batch: "免费版每次限批量 3 条，开通 VIP 解锁无限批量",
  generic: "该功能为 VIP 专享",
};

function showToast(text, ms = 2200) {
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = text;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), ms);
}

function showPayModal(reasonKey = "generic") {
  const modal = $("#payModal");
  const reason = $("#payReason");
  if (reason) reason.textContent = VIP_REASONS[reasonKey] || VIP_REASONS.generic;
  modal.hidden = false;
}

function hidePayModal() {
  $("#payModal").hidden = true;
}

function setupModal() {
  document.querySelectorAll("[data-close]").forEach((el) => {
    el.addEventListener("click", hidePayModal);
  });
  const payBtn = $("#payBtn");
  if (payBtn) {
    payBtn.addEventListener("click", () => {
      showToast("正在跳转到支付页面，请稍候...");
      setTimeout(() => {
        showToast("支付通道维护中，请添加客服微信：fvd-vip");
      }, 1500);
    });
  }
}

function setupVipTriggers() {
  document.querySelectorAll("[data-vip]").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      showPayModal(el.dataset.vip || "generic");
    });
  });
  const topVip = $("#topVipBtn");
  if (topVip) topVip.addEventListener("click", () => showPayModal("generic"));
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (m) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[m]);
}

function renderFormats(formats, serverHasFfmpeg) {
  const ul = $("#formats");
  ul.innerHTML = "";
  if (!formats || !formats.length) {
    ul.innerHTML = '<li class="result-error" style="grid-column:1/-1">未找到可用格式</li>';
    return;
  }

  formats.forEach((fmt, idx) => {
    const li = document.createElement("li");
    const blockedByFfmpeg = fmt.needs_merge && !serverHasFfmpeg;
    li.className = "format-item"
      + (fmt.is_vip ? " vip" : "")
      + (blockedByFfmpeg ? " disabled" : "");
    const meta = [];
    if (fmt.filesize_human) meta.push(fmt.filesize_human);
    if (fmt.fps) meta.push(`${fmt.fps}fps`);
    if (fmt.needs_merge) meta.push(blockedByFfmpeg ? "需 ffmpeg" : "需合并");
    li.innerHTML = `
      <div class="format-left">
        <span class="format-res">${escapeHtml(fmt.resolution)}</span>
        <span class="format-ext">${escapeHtml(fmt.ext || "")}</span>
        ${fmt.is_vip ? '<span class="vip-badge">VIP</span>' : ""}
        <span class="format-meta">${escapeHtml(meta.join(" · "))}</span>
      </div>
      <button class="btn-dl ${fmt.is_vip ? "vip" : ""}" ${blockedByFfmpeg ? "disabled" : ""} data-idx="${idx}" title="${blockedByFfmpeg ? "服务器未装 ffmpeg，无法合并音视频" : ""}">
        ${blockedByFfmpeg ? "不可用" : (fmt.is_vip ? "VIP 下载" : "下载")}
      </button>
    `;
    const btn = li.querySelector(".btn-dl");
    if (blockedByFfmpeg) {
      btn.addEventListener("click", () =>
        showToast("此格式需音视频合并，服务器未装 ffmpeg。请改选无标记格式 ↑", 3500)
      );
    } else {
      btn.addEventListener("click", () => downloadFormat(fmt, btn));
    }
    ul.appendChild(li);
  });
}

function renderVideoInfo(info) {
  $("#videoThumb").src = info.thumbnail || "";
  $("#videoTitle").textContent = info.title;
  $("#videoDuration").textContent = info.duration_human || "";
  $("#videoDuration").hidden = !info.duration_human;
  $("#videoUploader").textContent = info.uploader || "未知作者";
  $("#videoSource").textContent = info.extractor || "";

  let banner = $("#ffmpegBanner");
  if (info.server_has_ffmpeg === false) {
    if (!banner) {
      banner = document.createElement("div");
      banner.id = "ffmpegBanner";
      banner.className = "ffmpeg-banner";
      banner.innerHTML = `
        <b>提示：</b>服务器未安装 ffmpeg，标记「需合并」的高清格式不可用。
        请选择无标记的格式下载；如需 1080p+ 完整画质，请在服务器
        <a href="https://www.gyan.dev/ffmpeg/builds/" target="_blank" rel="noopener">安装 ffmpeg</a> 后重启服务。
      `;
      $(".formats-title").insertAdjacentElement("beforebegin", banner);
    }
    banner.hidden = false;
  } else if (banner) {
    banner.hidden = true;
  }

  renderFormats(info.formats, info.server_has_ffmpeg !== false);
  $("#videoCard").hidden = false;
}

async function handleParse(e) {
  e.preventDefault();
  const url = $("#urlInput").value.trim();
  if (!url) return;

  state.currentUrl = url;

  $("#result").hidden = false;
  $("#resultLoading").hidden = false;
  $("#resultError").hidden = true;
  $("#videoCard").hidden = true;
  $("#parseBtn").disabled = true;

  try {
    const res = await fetch("/api/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const json = await res.json();
    if (!res.ok || !json.ok) {
      throw new Error(json.detail || "解析失败，请稍后再试");
    }
    state.currentInfo = json.data;
    renderVideoInfo(json.data);
    $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    const errEl = $("#resultError");
    errEl.textContent = "❗ " + (err.message || "未知错误");
    errEl.hidden = false;
  } finally {
    $("#resultLoading").hidden = true;
    $("#parseBtn").disabled = false;
  }
}

function triggerBrowserDownload(url, filename) {
  return new Promise((resolve, reject) => {
    try {
      const a = document.createElement("a");
      a.href = url;
      a.download = filename || "";
      a.rel = "noopener";
      a.target = "_blank";
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        a.remove();
        resolve();
      }, 100);
    } catch (e) {
      reject(e);
    }
  });
}

async function downloadFormat(fmt, btn) {
  if (fmt.is_vip) return showPayModal("format");
  if (state.busyFormatId === fmt.format_id) return;

  const title = (state.currentInfo && state.currentInfo.title) || "video";
  const safeTitle = title.replace(/[\\/:*?"<>|]/g, "_").slice(0, 80);
  const filename = `${safeTitle}.${fmt.ext || "mp4"}`;

  const originalText = btn.textContent;
  btn.disabled = true;
  state.busyFormatId = fmt.format_id;

  try {
    // Strategy 1: direct URL when both video+audio present and url available
    if (fmt.has_audio && fmt.has_video && fmt.url && !fmt.needs_merge) {
      btn.textContent = "准备下载...";
      try {
        await triggerBrowserDownload(fmt.url, filename);
        showToast("已开始下载，请查看浏览器下载列表");
        return;
      } catch (e) {
        // fall through to server proxy
      }
    }

    // Strategy 2: server-side proxy (merge or fallback)
    btn.textContent = fmt.needs_merge ? "音视频合并中..." : "服务器加速中...";
    const res = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: state.currentUrl,
        format_id: fmt.format_id,
        needs_merge: fmt.needs_merge,
      }),
    });
    const json = await res.json();
    if (!res.ok || !json.ok) {
      throw new Error(json.detail || "服务器下载失败");
    }
    btn.textContent = "传输中...";
    location.href = `/api/file/${json.file_id}`;
    showToast("已开始下载，请查看浏览器下载列表");
  } catch (e) {
    showToast("下载失败：" + (e.message || "未知错误"), 3500);
  } finally {
    setTimeout(() => {
      btn.disabled = false;
      btn.textContent = originalText;
      state.busyFormatId = null;
    }, 1200);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  setupModal();
  setupVipTriggers();
  $("#parseForm").addEventListener("submit", handleParse);

  // Auto-paste from clipboard hint (helps mobile UX)
  $("#urlInput").addEventListener("focus", async () => {
    if ($("#urlInput").value) return;
    try {
      const text = await navigator.clipboard.readText();
      if (text && /^https?:\/\//.test(text)) {
        $("#urlInput").value = text.trim();
      }
    } catch (e) { /* clipboard read may be blocked, ignore */ }
  });
});

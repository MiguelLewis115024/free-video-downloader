/**
 * Batch download page logic.
 * - Counts URLs as user types
 * - Warns when over free quota (server enforces too)
 * - Renders parsed result cards
 */

const $ = (sel) => document.querySelector(sel);

const FREE_LIMIT = 3;

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
  $("#payReason").textContent = VIP_REASONS[reasonKey] || VIP_REASONS.generic;
  $("#payModal").hidden = false;
}
function hidePayModal() { $("#payModal").hidden = true; }

function setupModal() {
  document.querySelectorAll("[data-close]").forEach((el) =>
    el.addEventListener("click", hidePayModal)
  );
  $("#payBtn").addEventListener("click", () => {
    showToast("正在跳转到支付页面，请稍候...");
    setTimeout(() => showToast("支付通道维护中，请添加客服微信：fvd-vip"), 1500);
  });
}

function setupVipTriggers() {
  document.querySelectorAll("[data-vip]").forEach((el) =>
    el.addEventListener("click", (e) => {
      e.preventDefault();
      showPayModal(el.dataset.vip || "generic");
    })
  );
  $("#topVipBtn").addEventListener("click", () => showPayModal("generic"));
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (m) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[m]);
}

function parseUrls(text) {
  return text
    .split(/\s+/)
    .map((s) => s.trim())
    .filter((s) => /^https?:\/\//.test(s));
}

function updateCount() {
  const urls = parseUrls($("#batchUrls").value);
  $("#batchCount").textContent = urls.length;
  $("#batchOverHint").hidden = urls.length <= FREE_LIMIT;
}

function pickFreeFormat(formats, serverHasFfmpeg) {
  if (!formats || !formats.length) return null;
  return (
    formats.find(
      (f) => f.has_video && f.has_audio && !f.is_vip && !f.needs_merge
    ) ||
    (serverHasFfmpeg
      ? formats.find((f) => f.has_video && !f.is_vip)
      : null) ||
    formats.find((f) => !f.is_vip) ||
    formats[0]
  );
}

async function downloadFromBatch(url, fmt, btn) {
  if (!fmt) return;
  if (fmt.is_vip) return showPayModal("format");
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = "下载中...";
  try {
    if (fmt.has_audio && fmt.has_video && fmt.url && !fmt.needs_merge) {
      const a = document.createElement("a");
      a.href = fmt.url;
      a.download = "";
      a.target = "_blank";
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      a.remove();
      showToast("已开始下载");
      return;
    }
    const res = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        format_id: fmt.format_id,
        needs_merge: fmt.needs_merge,
      }),
    });
    const json = await res.json();
    if (!res.ok || !json.ok) throw new Error(json.detail || "下载失败");
    window.open(`/api/file/${json.file_id}`, "_blank");
    showToast("已开始下载");
  } catch (e) {
    showToast("下载失败：" + (e.message || "未知错误"), 3500);
  } finally {
    setTimeout(() => {
      btn.disabled = false;
      btn.textContent = original;
    }, 1200);
  }
}

function renderResults(payload) {
  const ul = $("#batchResults");
  ul.innerHTML = "";

  payload.results.forEach((r) => {
    const li = document.createElement("li");
    if (!r.ok) {
      li.className = "batch-result-item error";
      li.innerHTML = `
        <div class="batch-result-thumb"></div>
        <div class="batch-result-info">
          <h4>${escapeHtml(r.url)}</h4>
          <p class="err">❗ ${escapeHtml(r.error || "解析失败")}</p>
        </div>
        <div class="batch-result-actions"></div>
      `;
      ul.appendChild(li);
      return;
    }

    const data = r.data;
    const freeFmt = pickFreeFormat(data.formats, data.server_has_ffmpeg !== false);
    li.className = "batch-result-item";
    li.innerHTML = `
      <div class="batch-result-thumb">${
        data.thumbnail ? `<img src="${escapeHtml(data.thumbnail)}" alt="">` : ""
      }</div>
      <div class="batch-result-info">
        <h4>${escapeHtml(data.title)}</h4>
        <p>${escapeHtml(data.uploader || "")} ${data.duration_human ? "· " + data.duration_human : ""} · ${escapeHtml(data.extractor || "")}</p>
        <p style="color:var(--text-3);">默认下载：${escapeHtml(freeFmt ? freeFmt.resolution : "无可用格式")}</p>
      </div>
      <div class="batch-result-actions">
        <button class="btn-dl btn-go">下载</button>
        <button class="btn-ai" data-vip="ai"><span class="crown"></span>AI 总结</button>
      </div>
    `;
    const btn = li.querySelector(".btn-go");
    btn.addEventListener("click", () => downloadFromBatch(r.url, freeFmt, btn));
    li.querySelector("[data-vip]").addEventListener("click", (e) => {
      e.preventDefault();
      showPayModal("ai");
    });
    ul.appendChild(li);
  });

  if (payload.over_limit) {
    const card = document.createElement("li");
    card.className = "batch-overflow-card";
    card.innerHTML = `
      <p>还有 ${payload.vip_required_count} 条链接超出免费额度，开通 VIP 立即全部解锁 ⚡</p>
      <button class="btn-vip-pill"><span class="crown"></span>升级 VIP 解锁</button>
    `;
    card.querySelector("button").addEventListener("click", () => showPayModal("batch"));
    $("#batchResults").appendChild(card);
  }
}

async function handleBatch() {
  const urls = parseUrls($("#batchUrls").value);
  if (urls.length === 0) {
    showToast("请输入至少一条有效链接");
    return;
  }
  if (urls.length > FREE_LIMIT) {
    // Server will also enforce, but warn the user up front.
    showPayModal("batch");
  }

  $("#result").hidden = false;
  $("#resultLoading").hidden = false;
  $("#batchResults").innerHTML = "";
  $("#batchBtn").disabled = true;

  try {
    const res = await fetch("/api/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls }),
    });
    const json = await res.json();
    if (!res.ok || !json.ok) throw new Error(json.detail || "批量解析失败");
    renderResults(json);
  } catch (e) {
    $("#batchResults").innerHTML = `<li class="result-error">❗ ${escapeHtml(e.message)}</li>`;
  } finally {
    $("#resultLoading").hidden = true;
    $("#batchBtn").disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  setupModal();
  setupVipTriggers();
  $("#batchUrls").addEventListener("input", updateCount);
  $("#batchBtn").addEventListener("click", handleBatch);
  updateCount();
});

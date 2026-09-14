// Browser Bridge popup - 显示连接状态
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");

// 版本号从 manifest 读取，避免 popup 文案与 manifest 版本漂移
const verEl = document.getElementById("ver");
if (verEl) verEl.textContent = chrome.runtime.getManifest().version;

// 通过 badge text 间接判断连接状态
chrome.action.getBadgeText({}, (text) => {
  if (text === "ON") {
    statusDot.className = "dot on";
    statusText.textContent = "已连接";
  } else {
    statusDot.className = "dot off";
    statusText.textContent = "未连接";
  }
});

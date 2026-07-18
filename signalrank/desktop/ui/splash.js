const retry = document.querySelector("#retry");
const openLog = document.querySelector("#open-log");

retry?.addEventListener("click", async () => {
  retry.disabled = true;
  document.querySelector(".status").textContent = "Restarting SignalRank…";
  await window.__TAURI__.core.invoke("restart_app");
});

openLog?.addEventListener("click", async () => {
  await window.__TAURI__.core.invoke("reveal_startup_log");
});

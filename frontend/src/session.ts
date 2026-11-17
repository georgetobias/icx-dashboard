// One connection per tab. Page refresh has an 8-second reconnect grace period;
// background tabs need no JavaScript heartbeat timers to remain open.
export function startBrowserSession() {
  let socket: WebSocket | null = null;
  let retry: ReturnType<typeof setTimeout> | undefined;
  let hiddenPage = false;
  const connect = () => {
    clearTimeout(retry);
    if (hiddenPage || socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) return;
    socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/session`);
    socket.onclose = () => { if (!hiddenPage) retry = setTimeout(connect, 1000); };
    socket.onerror = () => socket?.close();
  };
  window.addEventListener("pagehide", () => {
    hiddenPage = true;
    clearTimeout(retry);
    socket?.close(1000, "Dashboard tab closed");
    socket = null;
  });
  window.addEventListener("pageshow", () => { hiddenPage = false; connect(); });
  connect();
}

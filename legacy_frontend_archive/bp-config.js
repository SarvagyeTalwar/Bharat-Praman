(function () {
  // Native mode: UI on 5500, API on 8000, RTI on 8001, same host.
  // Proxied/Docker mode: served on any other port, so use same-origin paths.
  const host = window.location.hostname || "127.0.0.1";
  const port = window.location.port;
  const native = port === "5500" || port === "8001";
  window.BP_CONFIG = window.BP_CONFIG || {
    apiBase: native ? `http://${host}:8000` : "",
    rtiBase: native && port !== "8001" ? `http://${host}:8001` : ""
  };
})();

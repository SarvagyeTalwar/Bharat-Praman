(function () {
  // Determine API base host: use window.location.hostname or fall back to 127.0.0.1
  const host = (window.location.hostname && window.location.hostname !== "") ? window.location.hostname : "127.0.0.1";
  const port = window.location.port;
  
  // If explicitly hosted behind a reverse proxy / production domain on ports 80/443 without port in URL:
  const isProxied = (port === "80" || port === "443" || (window.location.protocol.startsWith("http") && !port));

  window.BP_CONFIG = window.BP_CONFIG || {
    apiBase: isProxied ? "" : `http://${host}:8000`,
    rtiBase: isProxied ? "/rti" : `http://${host}:8001`
  };
})();


(function () {
  const STORAGE_KEY = "asset_base_url_v1";
  const DEFAULT_ASSET_BASE_URL = "https://pub-f7419ca433e9434bad2f9e89e252c205.r2.dev";
  const ASSET_VERSION = "20260308-physics-fix-1";

  function normalizeBase(raw) {
    const value = String(raw || "").trim();
    if (!value) {
      return "";
    }
    return value.replace(/\/+$/, "");
  }

  function getBase() {
    const host = String(window.location && window.location.hostname ? window.location.hostname : "").toLowerCase();
    // In local dev, use same-origin relative paths to avoid cross-origin fetch/CORS issues.
    if (host === "localhost" || host === "127.0.0.1") {
      return "";
    }
    const fromWindow = normalizeBase(window.ASSET_BASE_URL);
    if (fromWindow) {
      return fromWindow;
    }
    try {
      const fromStorage = normalizeBase(window.localStorage.getItem(STORAGE_KEY));
      if (fromStorage) {
        return fromStorage;
      }
    } catch (_error) {
      // Ignore storage failures and fall back to default.
    }
    return normalizeBase(DEFAULT_ASSET_BASE_URL);
  }

  function isAbsoluteUrl(path) {
    return /^https?:\/\//i.test(path) || /^\/\//.test(path);
  }

  function assetUrl(path) {
    const rawPath = String(path || "");
    if (!rawPath) {
      return rawPath;
    }
    if (isAbsoluteUrl(rawPath)) {
      return rawPath;
    }
    const base = getBase();
    if (!base) {
      return rawPath;
    }
    if (rawPath.startsWith("/")) {
      return withVersion(`${base}${rawPath}`);
    }
    return withVersion(`${base}/${rawPath}`);
  }

  function withVersion(url) {
    if (!ASSET_VERSION || !url) {
      return url;
    }
    const joiner = url.includes("?") ? "&" : "?";
    return `${url}${joiner}v=${encodeURIComponent(ASSET_VERSION)}`;
  }

  function setAssetBaseUrl(nextBase) {
    const value = normalizeBase(nextBase);
    try {
      if (value) {
        window.localStorage.setItem(STORAGE_KEY, value);
      } else {
        window.localStorage.removeItem(STORAGE_KEY);
      }
    } catch (_error) {
      // Ignore storage failures.
    }
    return value;
  }

  window.getAssetBaseUrl = getBase;
  window.setAssetBaseUrl = setAssetBaseUrl;
  window.assetUrl = assetUrl;
  window.assetFetch = function assetFetch(path, init) {
    return fetch(assetUrl(path), init);
  };
})();

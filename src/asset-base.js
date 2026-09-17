(function () {
  const STORAGE_KEY = "asset_base_url_v1";
  const DEFAULT_ASSET_BASE_URL = "https://pub-f7419ca433e9434bad2f9e89e252c205.r2.dev";
  const ASSET_VERSION = "20260308-physics-fix-1";
  const LOCAL_ASSET_PATHS = new Set([
    "/data/physics/processed/images/markschemes/phys_m17_p3_tz2_q13_hl.png",
    "/data/physics/processed/images/markschemes/phys_m17_p3_tz2_q9_sl.png",
  ]);

  function normalizeBase(raw) {
    const value = String(raw || "").trim();
    if (!value) {
      return "";
    }
    return value.replace(/\/+$/, "");
  }

  function getBase() {
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
    if (LOCAL_ASSET_PATHS.has(rawPath)) {
      return withVersion(rawPath);
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
    const cleanPath = String(path || "");
    // JSON files are served same-origin from the Docker container on all environments.
    // Only binary assets (images, PDFs) are served from the R2 CDN.
    if (cleanPath.endsWith(".json")) {
      return fetch(cleanPath, init);
    }
    return fetch(assetUrl(cleanPath), init);
  };
})();

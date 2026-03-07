(function () {
  const STORAGE_KEY = "asset_base_url_v1";

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
      return normalizeBase(window.localStorage.getItem(STORAGE_KEY));
    } catch (_error) {
      return "";
    }
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
      return `${base}${rawPath}`;
    }
    return `${base}/${rawPath}`;
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

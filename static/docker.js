// Docker features of the portal: the Nexus registry catalog (Docker tab, Docker Hub-style image pages) and
// the Docker Image Builder tool on the Actions hub (ZIP to image, live build terminal over SSE via XHR).
// The whole Docker ecosystem is English-only and left-to-right, whatever the portal language.
(() => {
  "use strict";

  const { esc, icon, toast } = window.PAKAL;

  const API = {
    config: "/api/docker/config",
    images: "/api/docker/images",
    image: "/api/docker/image",
    build: "/api/docker/build-and-push",
  };
  const IMAGE_NAME_RE = /^[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*(?:\/[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*){0,3}$/;
  const TAG_RE = /^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$/;
  const MAX_TERMINAL_LINES = 4000;
  const PHASES = ["upload", "extract", "build", "push", "cleanup"];
  const BUSY = new Set(["uploading", "running"]);
  const MODAL_TABS = ["overview", "tags", "config"];
  const WEB_PORTS = new Set([80, 443, 3000, 4200, 5000, 5173, 8000, 8080, 8081, 8443, 8888, 9000, 9090]);
  // Image internals that make no sense to set in a compose file.
  const INTERNAL_ENV = /^(PATH|HOME|HOSTNAME|TERM|SHLVL|LANG|LANGUAGE|LC_[A-Z]+|GPG_KEY|.*_(VERSION|SHA256|SHA|CHECKSUM))$/;

  const S = {
    title: "Docker Catalog",
    subtitle: "Images in the organizational registry - pull and run with one command.",
    search: "Search images…",
    refresh: "Refresh",
    notConfigured: "The Docker registry is not configured",
    notConfiguredText: "An administrator needs to set the registry address in the admin console (Nexus → Docker Registry).",
    loadError: "Could not load the image catalog",
    retry: "Retry",
    empty: "No images in the registry yet",
    emptyText: "Images pushed to the registry (for example with the Docker Image Builder on the Actions hub) appear here.",
    noMatch: "No matching images",
    noMatchText: "Try a different search term.",
    count: (n) => (n === 1 ? "1 image" : `${n} images`),
    tags: (n) => (n === 1 ? "1 tag" : `${n} tags`),
    noTags: "No tags",
    tagError: "Could not load tags",
    updated: (time) => `Updated ${time}`,
    copied: "Copied to clipboard",
    copyFailed: "Copy failed - select the text and copy it manually",
    detailsLoading: "Loading image details…",
    detailsError: "Could not load the image details",
    // build tool
    bNeedZip: "Choose a ZIP file",
    bNotZip: "Only .zip files can be built",
    bTooLarge: (mb) => `The file is larger than ${mb} MB`,
    bBadName: "Invalid image name",
    bBadTag: "Invalid tag",
    bBadDockerfile: "Invalid Dockerfile path",
    bNameHint: "Lowercase letters, digits and . _ - (sub-paths with /)",
    bTagHint: "For example latest or 1.4.2",
    bDockerfileHint: "Relative to the ZIP root",
    bUploading: (pct) => `Uploading the ZIP… ${pct}%`,
    bQueued: "Uploaded - starting the build…",
    phase: { upload: "Upload", extract: "Extract", build: "Build", push: "Push", cleanup: "Clean up" },
    bRunning: { extract: "Extracting the project…", build: "Building the image…", push: "Pushing to the registry…", cleanup: "Cleaning up…" },
    bDone: (sec) => `Image pushed successfully (${sec}s)`,
    bFailed: "The build failed",
    bCancelled: "Build cancelled",
    bStreamEnded: "The connection closed before the build finished",
    bNetwork: "Network error - could not reach the server",
    bLeave: "A build is still running. Leaving the page cancels it.",
  };

  const USE_CASE_RULES = [
    [/nginx|httpd|apache|caddy|traefik|haproxy|envoy/, ["Serve static websites and single-page apps", "Reverse proxy and TLS termination in front of internal services", "Load-balance traffic across several containers"]],
    [/postgres|mysql|mariadb|mssql|sqlserver|oracle|mongo|cockroach|timescale/, ["Development and test databases that start in seconds", "Persistent data store for internal applications (mount a named volume)", "Disposable databases for CI pipelines"]],
    [/redis|memcached|valkey|keydb/, ["Low-latency cache in front of APIs and databases", "Session store and rate-limiting counters", "Lightweight pub/sub message broker"]],
    [/rabbitmq|kafka|nats|activemq|mosquitto|emqx/, ["Asynchronous messaging between services", "Event streaming and background job queues"]],
    [/python|node|golang|openjdk|java|temurin|dotnet|aspnet|ruby|php|rust|gcc|maven|gradle/, ["Base image for building and running applications", "Reproducible build environment for CI jobs", "Run scripts without installing a toolchain locally"]],
    [/jenkins|gitlab|runner|drone|argo|tekton|sonar/, ["CI/CD automation for internal repositories", "Self-hosted build and analysis agents"]],
    [/grafana|prometheus|loki|elastic|kibana|opensearch|zabbix|telegraf|influx|jaeger/, ["Monitoring dashboards and metrics collection", "Centralised logging, tracing and alerting"]],
    [/ubuntu|debian|alpine|centos|rocky|alma|rhel|ubi|busybox|fedora/, ["Minimal base image for custom builds", "Interactive troubleshooting shell (docker run -it --rm <image> sh)"]],
    [/vault|keycloak|openldap|ldap|authelia/, ["Identity, authentication and secrets management for internal apps"]],
    [/minio|nexus|artifactory|registry|harbor/, ["Artifact and object storage for internal tooling"]],
  ];

  const state = {
    view: null,
    tool: null,
    auth: null,
    config: null,
    configError: null,
    images: null,
    imagesError: null,
    imagesLoading: false,
    fetchedAt: null,
    search: "",
    modal: null,
    details: new Map(),
    build: newBuild(),
    wrap: true,
  };

  function newBuild(keep = {}) {
    return {
      file: null, image: "", tag: "latest", dockerfile: "Dockerfile", touched: {},
      status: "idle", phase: null, pct: 0, error: "", result: null, xhr: null, startedAt: 0,
      lines: [], ...keep,
    };
  }

  const $ = (selector, root = document) => root.querySelector(selector);

  function t(key, ...args) {
    const value = S[key] ?? key;
    return typeof value === "function" ? value(...args) : value;
  }

  const mono = (text) => `<code class="dk-mono">${esc(text)}</code>`;

  function humanBytes(n) {
    if (!n && n !== 0) return "";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let value = Number(n);
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
      value /= 1024;
      unit += 1;
    }
    return `${value.toFixed(unit && value < 10 ? 1 : 0)} ${units[unit]}`;
  }

  function formatDate(value, style = "medium") {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString("en-GB", style === "date" ? { dateStyle: "medium" } : { dateStyle: "medium", timeStyle: "short" });
  }

  function timeAgo(value) {
    const date = new Date(value);
    if (!value || Number.isNaN(date.getTime())) return "";
    const sec = Math.max(0, (Date.now() - date.getTime()) / 1000);
    const steps = [[60, "second"], [60, "minute"], [24, "hour"], [30, "day"], [12, "month"], [Infinity, "year"]];
    let amount = sec;
    for (const [size, unit] of steps) {
      if (amount < size) {
        const n = Math.max(1, Math.floor(amount));
        return `${n} ${unit}${n === 1 ? "" : "s"} ago`;
      }
      amount /= size;
    }
    return "";
  }

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store", credentials: "same-origin" });
    let body = null;
    try { body = await response.json(); } catch (_) { /* non-JSON */ }
    if (!response.ok) throw new Error((body && typeof body.detail === "string" && body.detail) || `${response.status} ${response.statusText}`);
    return body;
  }

  function emptyState(title, text, iconName = "container", action = "") {
    return `<div class="empty"><span class="empty-icon">${icon(iconName)}</span><h3>${esc(title)}</h3><p>${esc(text)}</p>${action}</div>`;
  }

  async function copyText(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.cssText = "position:fixed;top:-1000px;opacity:0";
        document.body.appendChild(area);
        area.select();
        const ok = document.execCommand("copy");
        area.remove();
        if (!ok) throw new Error("copy");
      }
      toast(t("copied"), "success", 1800);
      return true;
    } catch (_) {
      toast(t("copyFailed"), "error");
      return false;
    }
  }

  // ------------------------------------------------------------------ markdown

  // A small, escape-first Markdown renderer for image READMEs: headings, paragraphs, lists, quotes, tables,
  // fenced code, inline code, emphasis and http(s) links. Raw HTML is never passed through.
  function inlineMd(text) {
    return text.split(/(`[^`]+`)/g).map((part) => {
      if (/^`[^`]+`$/.test(part)) return `<code>${esc(part.slice(1, -1))}</code>`;
      let html = esc(part);
      const link = (label, url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`;
      html = html.replace(/!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/g, (_m, alt, url) => link(alt || url, url));
      html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_m, label, url) => link(label, url));
      html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/__([^_]+)__/g, "<strong>$1</strong>");
      html = html.replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?!\w)/g, "$1<em>$2</em>");
      return html;
    }).join("");
  }

  function codeBlock(text, lang = "") {
    return `
      <div class="dk-codeblock">
        <div class="dk-codeblock-head"><span>${esc(lang || "text")}</span><button class="dk-codeblock-copy" type="button" data-dk="copy-code">${icon("copy")}<span>Copy</span></button></div>
        <pre><code>${esc(text)}</code></pre>
      </div>`;
  }

  function renderMarkdown(source) {
    const lines = String(source || "").replace(/\r\n?/g, "\n").split("\n");
    const out = [];
    let para = [];
    const flush = () => {
      if (para.length) out.push(`<p>${inlineMd(para.join(" "))}</p>`);
      para = [];
    };
    const cells = (row) => row.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
    const listItem = /^\s*(?:[-*+]|\d+[.)])\s+/;
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      const fence = line.match(/^\s*(```|~~~)\s*([\w+#.-]*)/);
      if (fence) {
        flush();
        const body = [];
        i += 1;
        while (i < lines.length && !lines[i].trim().startsWith(fence[1])) body.push(lines[i++]);
        i += 1;
        out.push(codeBlock(body.join("\n"), fence[2]));
        continue;
      }
      if (!line.trim()) {
        flush();
        i += 1;
        continue;
      }
      const heading = line.match(/^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$/);
      if (heading) {
        flush();
        const level = Math.min(6, heading[1].length + 2);
        out.push(`<h${level}>${inlineMd(heading[2])}</h${level}>`);
        i += 1;
        continue;
      }
      if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) {
        flush();
        out.push("<hr>");
        i += 1;
        continue;
      }
      if (/^\s*>/.test(line)) {
        flush();
        const quote = [];
        while (i < lines.length && /^\s*>/.test(lines[i])) quote.push(lines[i++].replace(/^\s*>\s?/, ""));
        out.push(`<blockquote>${inlineMd(quote.join(" "))}</blockquote>`);
        continue;
      }
      if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
        flush();
        const head = cells(line);
        i += 2;
        const rows = [];
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(cells(lines[i++]));
        out.push(`<div class="table-wrap"><table class="table"><thead><tr>${head.map((h) => `<th>${inlineMd(h)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${head.map((_h, c) => `<td>${inlineMd(r[c] || "")}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
        continue;
      }
      if (listItem.test(line)) {
        flush();
        const ordered = /^\s*\d/.test(line);
        const items = [];
        while (i < lines.length && listItem.test(lines[i])) {
          items.push(lines[i++].replace(listItem, ""));
          while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !listItem.test(lines[i])) items[items.length - 1] += ` ${lines[i++].trim()}`;
        }
        const tag = ordered ? "ol" : "ul";
        out.push(`<${tag}>${items.map((it) => `<li>${inlineMd(it)}</li>`).join("")}</${tag}>`);
        continue;
      }
      para.push(line.trim());
      i += 1;
    }
    flush();
    return out.join("");
  }

  // ------------------------------------------------------------------ config

  async function loadConfig() {
    try {
      state.config = await fetchJson(API.config);
      state.configError = null;
    } catch (err) {
      state.configError = err.message;
    }
    renderBuildCard();
  }

  // ----------------------------------------------------------------- catalog

  async function loadImages({ fresh = false } = {}) {
    if (state.imagesLoading) return;
    state.imagesLoading = true;
    renderCatalog();
    try {
      const data = await fetchJson(`${API.images}${fresh ? "?fresh=1" : ""}`);
      state.images = data.images || [];
      state.fetchedAt = data.fetched_at || Date.now() / 1000;
      state.imagesError = null;
      if (state.config) state.config.registry = data.registry || state.config.registry;
    } catch (err) {
      state.imagesError = err.message;
    } finally {
      state.imagesLoading = false;
      renderCatalog();
    }
  }

  const shortName = (name) => name.split("/").pop();
  const safeName = (name) => shortName(name).replace(/[^a-zA-Z0-9_.-]/g, "-");

  function filteredImages() {
    const q = state.search.trim().toLowerCase();
    const list = state.images || [];
    return q ? list.filter((img) => img.name.toLowerCase().includes(q) || (img.tags || []).some((tg) => tg.toLowerCase().includes(q))) : list;
  }

  function imageCard(img) {
    const namespace = img.name.includes("/") ? img.name.slice(0, img.name.lastIndexOf("/")) : "";
    const badge = img.error
      ? `<span class="badge badge-danger">${esc(t("tagError"))}</span>`
      : img.latest ? `<span class="badge badge-accent dk-tag-badge">${icon("tag")}${esc(img.latest)}</span>`
        : `<span class="badge badge-neutral">${esc(t("noTags"))}</span>`;
    return `
      <button class="card dk-card" type="button" data-dk="open" data-name="${esc(img.name)}">
        <span class="dk-glyph">${icon("container")}</span>
        <span class="dk-card-body">
          <strong>${esc(shortName(img.name))}</strong>
          ${namespace ? `<span class="dk-card-ns">${esc(namespace)}/</span>` : ""}
          <span class="dk-card-meta">${badge}${img.tag_count ? `<span class="dk-card-count">${esc(t("tags", img.tag_count))}</span>` : ""}</span>
        </span>
      </button>`;
  }

  function renderCatalog() {
    const root = $("#docker-root");
    if (!root) return;
    const cfg = state.config;
    const head = `
      <div class="page-head">
        <div>
          <h2 class="page-title">${esc(t("title"))}</h2>
          <p class="page-subtitle">${esc(t("subtitle"))}${cfg && cfg.registry ? ` <span class="dk-registry">${esc(cfg.registry)}</span>` : ""}</p>
        </div>
        ${cfg && cfg.catalog ? `
        <div class="toolbar dk-toolbar">
          <label class="search dk-search">
            ${icon("search")}
            <input type="search" id="dk-search" autocomplete="off" spellcheck="false" value="${esc(state.search)}" placeholder="${esc(t("search"))}" aria-label="${esc(t("search"))}">
          </label>
          <button class="btn btn-secondary" type="button" data-dk="refresh" ${state.imagesLoading ? "disabled" : ""}>${icon("refresh")}<span>${esc(t("refresh"))}</span></button>
        </div>` : ""}
      </div>`;
    let body;
    if (!cfg) {
      body = state.configError
        ? emptyState(t("loadError"), state.configError, "alert", `<button class="btn btn-secondary" type="button" data-dk="reload">${icon("refresh")}<span>${esc(t("retry"))}</span></button>`)
        : `<div class="grid grid-platforms">${'<div class="card dk-card dk-skeleton"></div>'.repeat(8)}</div>`;
    } else if (!cfg.catalog) {
      body = emptyState(t("notConfigured"), t("notConfiguredText"), "container");
    } else if (state.imagesError && !state.images) {
      body = emptyState(t("loadError"), state.imagesError, "alert", `<button class="btn btn-secondary" type="button" data-dk="refresh">${icon("refresh")}<span>${esc(t("retry"))}</span></button>`);
    } else if (!state.images) {
      body = `<div class="grid grid-platforms">${'<div class="card dk-card dk-skeleton"></div>'.repeat(8)}</div>`;
    } else if (!state.images.length) {
      body = emptyState(t("empty"), t("emptyText"), "container");
    } else {
      const list = filteredImages();
      const when = state.fetchedAt ? new Date(state.fetchedAt * 1000).toLocaleTimeString("en-GB", { timeStyle: "short" }) : "";
      body = `
        <div class="results-line"><span>${esc(t("count", list.length))}</span>${when ? `<span class="dk-updated">· ${esc(t("updated", when))}</span>` : ""}</div>
        ${list.length ? `<div class="grid grid-platforms dk-grid">${list.map(imageCard).join("")}</div>` : emptyState(t("noMatch"), t("noMatchText"), "search")}`;
    }
    const focused = document.activeElement && document.activeElement.id === "dk-search";
    const caret = focused ? document.activeElement.selectionStart : null;
    root.innerHTML = head + body;
    if (focused) {
      const input = $("#dk-search");
      input.focus();
      if (caret !== null) input.setSelectionRange(caret, caret);
    }
  }

  // ------------------------------------------------------------ image modal

  function openImage(name, tag = null) {
    state.modal = { name, tag, tab: "overview", loading: true, error: null, opener: document.activeElement };
    const backdrop = $("#docker-modal");
    backdrop.hidden = false;
    requestAnimationFrame(() => backdrop.classList.add("show"));
    document.body.classList.add("modal-open");
    renderModal();
    $("#docker-modal-close").focus();
    loadDetails(name, tag);
  }

  function closeImage() {
    if (!state.modal) return;
    const opener = state.modal.opener;
    state.modal = null;
    const backdrop = $("#docker-modal");
    backdrop.classList.remove("show");
    backdrop.hidden = true;
    $("#docker-modal-body").innerHTML = "";
    if ($("#modal").hidden) document.body.classList.remove("modal-open");
    if (opener && typeof opener.focus === "function") opener.focus();
  }

  async function loadDetails(name, tag) {
    const key = `${name}:${tag || ""}`;
    const cached = state.details.get(key);
    if (cached) {
      Object.assign(state.modal, { data: cached, tag: cached.tag, loading: false, error: null });
      renderModal();
      return;
    }
    const params = new URLSearchParams({ name });
    if (tag) params.set("tag", tag);
    try {
      const data = await fetchJson(`${API.image}?${params}`);
      state.details.set(`${name}:${data.tag}`, data);
      if (!tag) state.details.set(key, data);
      if (!state.modal || state.modal.name !== name) return;
      Object.assign(state.modal, { data, tag: data.tag, loading: false, error: null });
    } catch (err) {
      if (!state.modal || state.modal.name !== name) return;
      Object.assign(state.modal, { loading: false, error: err.message });
    }
    renderModal();
  }

  function selectTag(tag, tab = null) {
    const m = state.modal;
    if (!m || !tag) return;
    Object.assign(m, { tag, loading: true, tab: tab || m.tab });
    renderModal();
    loadDetails(m.name, tag);
  }

  const volumeName = (image, path) => {
    const slug = path.replace(/^\/+|\/+$/g, "").replace(/[^a-zA-Z0-9_.-]+/g, "-").replace(/^[-.]+|[-.]+$/g, "");
    return `${image}-${slug || "data"}`;
  };
  const portFlag = (p) => `-p ${p.port}:${p.port}${p.protocol && p.protocol !== "tcp" ? `/${p.protocol}` : ""}`;
  const secretEnv = (d) => (d.env || []).filter((e) => e.masked);

  function runCommand(d) {
    const name = safeName(d.name);
    const parts = ["docker run -d", `--name ${name}`];
    (d.ports || []).forEach((p) => parts.push(portFlag(p)));
    (d.volumes || []).forEach((v) => parts.push(`-v ${volumeName(name, v)}:${v}`));
    secretEnv(d).forEach((e) => parts.push(`-e ${e.key}=change-me`));
    parts.push(d.reference);
    return parts.join(" ");
  }

  function runCommandMultiline(d) {
    const name = safeName(d.name);
    const parts = ["docker run -d", `  --name ${name}`, "  --restart unless-stopped"];
    (d.ports || []).forEach((p) => parts.push(`  ${portFlag(p)}`));
    (d.volumes || []).forEach((v) => parts.push(`  -v ${volumeName(name, v)}:${v}`));
    secretEnv(d).forEach((e) => parts.push(`  -e ${e.key}=change-me`));
    parts.push(`  ${d.reference}`);
    return parts.join(" \\\n");
  }

  function composeYaml(d) {
    const name = safeName(d.name);
    const ports = d.ports || [];
    const volumes = d.volumes || [];
    const env = (d.env || []).filter((e) => !INTERNAL_ENV.test(e.key));
    const lines = ["services:", `  ${name}:`, `    image: ${d.reference}`, `    container_name: ${name}`, "    restart: unless-stopped"];
    if (ports.length) {
      lines.push("    ports:");
      ports.forEach((p) => lines.push(`      - "${p.port}:${p.port}${p.protocol && p.protocol !== "tcp" ? `/${p.protocol}` : ""}"`));
    }
    if (env.length) {
      lines.push("    environment:");
      env.forEach((e) => lines.push(`      ${e.key}: ${JSON.stringify(e.masked ? "change-me" : String(e.value ?? ""))}`));
    }
    if (volumes.length) {
      lines.push("    volumes:");
      volumes.forEach((v) => lines.push(`      - ${volumeName(name, v)}:${v}`));
      lines.push("", "volumes:");
      volumes.forEach((v) => lines.push(`  ${volumeName(name, v)}:`));
    }
    return lines.join("\n");
  }

  function useCases(d) {
    const haystack = `${d.name} ${d.description || ""}`.toLowerCase();
    const out = [];
    USE_CASE_RULES.forEach(([re, cases]) => { if (re.test(haystack)) out.push(...cases); });
    const ports = (d.ports || []).map((p) => Number(p.port));
    const web = ports.filter((p) => WEB_PORTS.has(p));
    if (web.length) out.push(`Web application or HTTP API reachable on port ${web.join(", ")}`);
    else if (ports.length) out.push(`Network service listening on port ${ports.join(", ")}`);
    if ((d.volumes || []).length) out.push("Stateful workloads - data lives in named volumes and survives upgrades");
    if (!ports.length) out.push("One-off jobs, batch tasks or CLI tools (docker run --rm)");
    if (d.labels && d.labels["pakal.built-by"]) out.push("Internal project image, built from source with the PAKAL Docker Image Builder");
    return [...new Set(out)].slice(0, 6);
  }

  function commandBox(command, label = "Copy command") {
    return `
      <div class="dk-cmd-box">
        <code><span class="dk-prompt" aria-hidden="true">$</span>${esc(command)}</code>
        <button class="btn btn-secondary btn-sm dk-copy" type="button" data-dk="copy-value" data-value="${esc(command)}" title="${esc(label)}" aria-label="${esc(label)}">${icon("copy")}<span>Copy</span></button>
      </div>`;
  }

  function panel(title, iconName, content, extra = "") {
    return `
      <section class="dk-panel">
        <header class="dk-panel-head"><span class="dk-panel-icon">${icon(iconName)}</span><h3>${esc(title)}</h3>${extra}</header>
        <div class="dk-panel-body">${content}</div>
      </section>`;
  }

  const countBadge = (n) => `<span class="dk-count">${n}</span>`;

  function overviewTab(d) {
    const ports = d.ports || [];
    const volumes = d.volumes || [];
    const readme = d.readme && d.readme.text;
    const intro = d.description || `${shortName(d.name)} is a container image published to the organizational registry${d.labels && d.labels["pakal.built-by"] ? " by the PAKAL Docker Image Builder" : ""}.`;
    const web = ports.find((p) => WEB_PORTS.has(Number(p.port)));
    const usage = `
      <div class="dk-md">
        <h3>How to use this image</h3>
        <h4>1. Pull the image</h4>
        ${codeBlock(`docker pull ${d.reference}`, "bash")}
        <h4>2. Start a container</h4>
        ${codeBlock(runCommandMultiline(d), "bash")}
        ${web ? `<p>Then open <code>http://localhost:${esc(web.port)}</code> in a browser.</p>` : ""}
        ${secretEnv(d).length ? `<p>Replace <code>change-me</code> with real values for ${secretEnv(d).map((e) => `<code>${esc(e.key)}</code>`).join(", ")}.</p>` : ""}
        <h4>3. Or run it with Docker Compose</h4>
        <p>Save as <code>docker-compose.yml</code> and run <code>docker compose up -d</code>:</p>
        ${codeBlock(composeYaml(d), "yaml")}
        ${ports.length ? `
        <h4>Port bindings</h4>
        <div class="table-wrap"><table class="table">
          <thead><tr><th>Container port</th><th>Protocol</th><th>Host binding</th></tr></thead>
          <tbody>${ports.map((p) => `<tr><td class="num">${esc(p.port)}</td><td><span class="badge badge-neutral">${esc((p.protocol || "tcp").toUpperCase())}</span></td><td>${mono(portFlag(p))}</td></tr>`).join("")}</tbody>
        </table></div>
        <p class="dk-note">Change the left-hand number to publish on a different host port, for example <code>-p 18080:${esc(ports[0].port)}</code>.</p>` : ""}
      </div>`;
    const cases = useCases(d);
    const about = [
      ["Tag", mono(d.tag)],
      ["OS / Arch", esc([d.os, d.architecture].filter(Boolean).join(" / ") || "—")],
      ["Compressed size", esc(d.size_bytes ? humanBytes(d.size_bytes) : "—")],
      ["Layers", esc(d.layers != null ? String(d.layers) : "—")],
      ["Created", d.created ? `<span title="${esc(formatDate(d.created))}">${esc(timeAgo(d.created) || formatDate(d.created))}</span>` : "—"],
      ["Exposed ports", ports.length ? ports.map((p) => `<span class="dk-chip">${esc(p.port)}/${esc(p.protocol || "tcp")}</span>`).join("") : "None"],
      ["Volumes", volumes.length ? volumes.map((v) => `<span class="dk-chip">${esc(v)}</span>`).join("") : "None"],
    ];
    return `
      <div class="dk-overview">
        <div class="dk-main">
          ${readme ? `
          <article class="dk-readme">
            <div class="dk-readme-head">${icon("book")}<span>README</span>${d.readme.tag ? `<span class="dk-readme-src">from the build of <code>${esc(d.readme.tag)}</code>${d.readme.updated_at ? ` · ${esc(timeAgo(d.readme.updated_at))}` : ""}</span>` : ""}</div>
            <div class="dk-md">${renderMarkdown(readme)}</div>
          </article>` : `<p class="dk-lead">${esc(intro)}</p>`}
          ${cases.length ? `
          <div class="dk-usecases">
            <h3>Recommended use cases</h3>
            <ul>${cases.map((c) => `<li>${icon("check")}<span>${esc(c)}</span></li>`).join("")}</ul>
          </div>` : ""}
          ${usage}
        </div>
        <aside class="dk-aside">
          <div class="dk-aside-card">
            <h4>About this image</h4>
            <dl>${about.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join("")}</dl>
            ${d.platforms && d.platforms.length > 1 ? `<h4>Platforms</h4><div class="dk-chips">${d.platforms.map((p) => `<span class="dk-chip">${esc(p)}</span>`).join("")}</div>` : ""}
            ${d.digest ? `<h4>Digest</h4><button class="dk-digest-btn" type="button" data-dk="copy-value" data-value="${esc(d.digest)}" title="Copy digest">${icon("lock")}<span>${esc(d.digest.slice(0, 19))}…</span>${icon("copy")}</button>` : ""}
          </div>
        </aside>
      </div>`;
  }

  function tagsTab(d) {
    const tags = d.tags || [];
    const base = d.reference.replace(/:[^:/]+$/, "");
    return panel("Tag history", "tag", `
      <div class="table-wrap"><table class="table dk-tags-table">
        <thead><tr><th>Tag</th><th>Pull command</th><th></th></tr></thead>
        <tbody>${tags.map((tg) => `
          <tr class="${tg === d.tag ? "is-current" : ""}">
            <td><span class="dk-tag-name">${icon("tag")}<span>${esc(tg)}</span></span>${tg === d.tag ? ' <span class="badge badge-accent">Viewing</span>' : ""}</td>
            <td>${mono(`docker pull ${base}:${tg}`)}</td>
            <td class="actions-cell">
              <button class="btn btn-ghost btn-sm" type="button" data-dk="copy-value" data-value="${esc(`docker pull ${base}:${tg}`)}">${icon("copy")}<span>Copy</span></button>
              ${tg === d.tag ? "" : `<button class="btn btn-secondary btn-sm" type="button" data-dk="view-tag" data-tag="${esc(tg)}">${icon("eye")}<span>View</span></button>`}
            </td>
          </tr>`).join("")}</tbody>
      </table></div>`, countBadge(tags.length));
  }

  function configTab(d) {
    const name = safeName(d.name);
    const ports = d.ports || [];
    const volumes = d.volumes || [];
    const env = d.env || [];
    const labels = Object.entries(d.labels || {});
    const runtime = [
      ["Entrypoint", d.entrypoint && d.entrypoint.length ? JSON.stringify(d.entrypoint) : ""],
      ["Command (CMD)", d.cmd && d.cmd.length ? JSON.stringify(d.cmd) : ""],
      ["Working directory", d.workdir || ""],
      ["User", d.user || ""],
    ];
    const empty = (text) => `<p class="dk-empty-line">${esc(text)}</p>`;
    return `
      <div class="dk-config">
        ${panel("Environment variables", "sliders", env.length ? `
          <div class="table-wrap"><table class="table dk-env">
            <thead><tr><th>Variable</th><th>Default value</th><th></th></tr></thead>
            <tbody>${env.map((e) => `
              <tr>
                <td><code class="dk-key">${esc(e.key)}</code>${INTERNAL_ENV.test(e.key) ? '<span class="dk-internal">image internal</span>' : ""}</td>
                <td>${e.masked ? '<span class="dk-masked" title="Hidden - looks like a secret">••••••••</span>' : e.value ? mono(e.value) : '<span class="muted">(empty)</span>'}</td>
                <td class="actions-cell"><button class="icon-btn icon-btn-sm" type="button" data-dk="copy-value" data-value="${esc(`-e ${e.key}=${e.masked ? "change-me" : e.value}`)}" title="Copy as -e flag" aria-label="Copy ${esc(e.key)} as -e flag">${icon("copy")}</button></td>
              </tr>`).join("")}</tbody>
          </table></div>` : empty("This image defines no environment variables."), countBadge(env.length))}
        <div class="dk-config-grid">
          ${panel("Exposed ports", "globe", ports.length ? `
            <div class="table-wrap"><table class="table">
              <thead><tr><th>Port</th><th>Protocol</th><th>Host binding</th></tr></thead>
              <tbody>${ports.map((p) => `<tr><td class="num">${esc(p.port)}</td><td><span class="badge badge-neutral">${esc((p.protocol || "tcp").toUpperCase())}</span></td><td>${mono(portFlag(p))}</td></tr>`).join("")}</tbody>
            </table></div>` : empty("No exposed ports - the image does not listen on the network."), countBadge(ports.length))}
          ${panel("Volumes", "hdd", volumes.length ? `
            <div class="table-wrap"><table class="table">
              <thead><tr><th>Container path</th><th>Suggested mount</th></tr></thead>
              <tbody>${volumes.map((v) => `<tr><td>${mono(v)}</td><td>${mono(`-v ${volumeName(name, v)}:${v}`)}</td></tr>`).join("")}</tbody>
            </table></div>` : empty("No declared volumes - the container keeps no persistent state."), countBadge(volumes.length))}
        </div>
        ${panel("Entrypoint & runtime", "terminal", `
          <dl class="dk-kv">${runtime.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${v ? mono(v) : '<span class="muted">Not set</span>'}</dd></div>`).join("")}</dl>`)}
        ${labels.length ? panel("Labels", "tag", `
          <div class="table-wrap"><table class="table dk-labels">
            <thead><tr><th>Key</th><th>Value</th></tr></thead>
            <tbody>${labels.map(([k, v]) => `<tr><td><code class="dk-key">${esc(k)}</code></td><td>${mono(v)}</td></tr>`).join("")}</tbody>
          </table></div>`, countBadge(labels.length)) : ""}
      </div>`;
  }

  function renderModal() {
    const m = state.modal;
    if (!m) return;
    const d = m.data;
    const tags = (d && d.tags) || [];
    const img = (state.images || []).find((i) => i.name === m.name);
    const tagCount = d ? tags.length : img ? img.tag_count : 0;
    const registry = (d && d.registry) || (state.config && state.config.registry) || "";
    const namespace = m.name.includes("/") ? m.name.slice(0, m.name.lastIndexOf("/")) : "";
    const select = tags.length ? `
      <label class="dk-tag-select">
        <span>${icon("tag")}Tag</span>
        <select class="select" id="dk-tag" aria-label="Tag history">
          ${tags.map((tg) => `<option value="${esc(tg)}" ${tg === m.tag ? "selected" : ""}>${esc(tg)}</option>`).join("")}
        </select>
      </label>` : "";
    const tabs = d ? `
      <div class="dk-tabs" role="tablist" aria-label="Image sections">
        ${MODAL_TABS.map((tab) => `<button class="dk-tab${m.tab === tab ? " active" : ""}" type="button" role="tab" aria-selected="${m.tab === tab}" data-dk="tab" data-tab="${tab}">${esc({ overview: "Overview", tags: "Tags", config: "Configuration" }[tab])}${tab === "tags" ? ` ${countBadge(tags.length)}` : ""}</button>`).join("")}
      </div>` : "";
    let body;
    if (m.error && !d) body = emptyState(t("detailsError"), m.error, "alert");
    else if (!d) body = `<div class="dk-loading" role="status"><span class="dk-spinner"></span>${esc(t("detailsLoading"))}</div>`;
    else {
      const content = m.tab === "tags" ? tagsTab(d) : m.tab === "config" ? configTab(d) : overviewTab(d);
      body = `${m.loading ? `<div class="dk-loading dk-loading-inline" role="status"><span class="dk-spinner"></span>${esc(t("detailsLoading"))}</div>` : ""}${m.error ? `<div class="notice">${icon("alert")}<span>${esc(m.error)}</span></div>` : ""}<div class="dk-tabpanel${m.loading ? " dk-stale" : ""}" role="tabpanel">${content}</div>`;
    }
    $("#docker-modal-body").innerHTML = `
      <div class="dk-hero">
        <div class="dk-hero-main">
          <span class="dk-glyph dk-glyph-lg">${icon("container")}</span>
          <div class="modal-heading">
            ${namespace ? `<span class="dk-hero-ns">${esc(namespace)} /</span>` : ""}
            <h2 id="dk-modal-title">${esc(shortName(m.name))}</h2>
            <div class="meta">
              <span class="dk-ref">${esc(registry ? `${registry}/${m.name}` : m.name)}</span>
              ${tagCount ? `<span class="badge badge-neutral">${esc(t("tags", tagCount))}</span>` : ""}
              ${d && d.created ? `<span class="dk-hero-updated">${icon("clock")}Updated ${esc(timeAgo(d.created))}</span>` : ""}
            </div>
          </div>
        </div>
        <div class="dk-hero-side">
          ${select}
          ${d ? `<div class="dk-pullbox"><span class="dk-pullbox-label">Docker Pull Command</span>${commandBox(`docker pull ${d.reference}`)}</div>` : ""}
        </div>
      </div>
      ${tabs}
      ${body}`;
  }

  // --------------------------------------------------------------- build tool

  const b = () => state.build;

  function buildAccess() {
    const cfg = state.config;
    if (!cfg || !cfg.build || !cfg.build.visible || !cfg.configured) return { show: false };
    const reason = cfg.build.reason;
    if (reason === "disabled" || reason === "not_configured" || reason === "admin_only") return { show: false };
    return { show: true, allowed: cfg.build.allowed, reason, engine: cfg.build.engine };
  }

  // Status of the Docker Image Builder card on the Actions hub (rendered by app.js).
  function hubStatus() {
    const cfg = state.config;
    if (!cfg) {
      return state.configError
        ? { loaded: true, visible: true, available: true, status: "Could not load the builder settings", tone: "bad" }
        : { loaded: false };
    }
    const build = cfg.build || {};
    const base = { loaded: true, visible: Boolean(build.visible) };
    if (!cfg.configured || build.reason === "not_configured") return { ...base, available: false, status: "Registry not configured", tone: "warn" };
    if (build.reason === "disabled") return { ...base, available: false, status: "Disabled by the administrator", tone: "muted" };
    if (build.reason === "admin_only") return { ...base, available: false, status: "Administrators only", tone: "muted" };
    const s = b();
    if (BUSY.has(s.status)) return { ...base, available: true, status: `Build running · ${statusLine()}`, tone: "busy" };
    if (build.reason === "sign_in") return { ...base, available: true, status: "Sign in to build", tone: "warn" };
    if (build.engine && !build.engine.available) return { ...base, available: true, status: "Docker engine unavailable", tone: "bad" };
    if (s.status === "done" && s.result) return { ...base, available: true, status: `Last build pushed · ${shortName(s.result.repository)}:${s.result.tag}`, tone: "ok" };
    if (s.status === "error") return { ...base, available: true, status: "Last build failed", tone: "bad" };
    return { ...base, available: true, status: `Ready · pushes to ${cfg.registry || "the registry"}`, tone: "ok" };
  }

  let lastHub = "";
  function emitHub() {
    const detail = hubStatus();
    const key = JSON.stringify(detail);
    if (key === lastHub) return;
    lastHub = key;
    document.dispatchEvent(new CustomEvent("pakal:docker-build", { detail }));
  }

  function targetRef() {
    const cfg = state.config || {};
    const parts = [cfg.registry, cfg.namespace, b().image || "…"].filter(Boolean);
    return `${parts.join("/")}:${b().tag || "latest"}`;
  }

  function formErrors() {
    const s = b();
    const errors = {};
    const maxMb = state.config && state.config.build ? state.config.build.max_context_mb : 0;
    if (!s.file) errors.file = t("bNeedZip");
    else if (!/\.zip$/i.test(s.file.name)) errors.file = t("bNotZip");
    else if (maxMb && s.file.size > maxMb * 1024 * 1024) errors.file = t("bTooLarge", maxMb);
    if (!IMAGE_NAME_RE.test(s.image)) errors.image = t("bBadName");
    if (!TAG_RE.test(s.tag)) errors.tag = t("bBadTag");
    const df = s.dockerfile.trim();
    if (!df || df.startsWith("/") || df.split(/[\\/]/).some((p) => p === "..")) errors.dockerfile = t("bBadDockerfile");
    return errors;
  }

  function suggestFromFile(file) {
    const base = file.name.replace(/\.zip$/i, "");
    const match = base.match(/^(.*?)[-_ ]v?(\d+(?:\.\d+)+(?:[-.][A-Za-z0-9.]+)?)$/);
    const rawName = match ? match[1] : base;
    const name = rawName.toLowerCase().replace(/[^a-z0-9._/-]+/g, "-").replace(/[-_.]{2,}/g, "-").replace(/^[^a-z0-9]+|[^a-z0-9]+$/g, "");
    const s = b();
    if (!s.touched.image && name) s.image = name.slice(0, 128);
    if (!s.touched.tag) s.tag = match ? match[2] : "latest";
  }

  function statusLine() {
    const s = b();
    switch (s.status) {
      case "uploading": return s.pct >= 100 ? t("bQueued") : t("bUploading", s.pct);
      case "running": return (t("bRunning")[s.phase]) || t("bQueued");
      case "done": return t("bDone", s.result ? s.result.seconds : 0);
      case "error": return s.error || t("bFailed");
      case "cancelled": return t("bCancelled");
      default: return "Idle";
    }
  }

  function phaseSteps() {
    const s = b();
    const current = s.status === "uploading" ? "upload" : s.phase;
    const index = PHASES.indexOf(current);
    return `<ol class="dk-phases" aria-label="Build progress">${PHASES.map((p, i) => {
      let cls = "";
      if (s.status === "done" || (index > i)) cls = "done";
      else if (i === index) cls = s.status === "error" || s.status === "cancelled" ? "failed" : BUSY.has(s.status) ? "active" : "";
      return `<li class="${cls}"><span class="dk-phase-dot">${cls === "done" ? icon("check") : cls === "failed" ? icon("x") : i + 1}</span><span>${esc(t("phase")[p])}</span></li>`;
    }).join("")}</ol>`;
  }

  function controlsHtml() {
    const s = b();
    const access = buildAccess();
    const busy = BUSY.has(s.status);
    const errors = formErrors();
    const locked = !access.allowed || (access.engine && !access.engine.available);
    const maxMb = state.config.build.max_context_mb;
    const fileChip = s.file ? `
      <div class="dk-file">
        <span class="dk-file-icon">${icon("file")}</span>
        <span class="dk-file-body"><strong>${esc(s.file.name)}</strong><span>${esc(humanBytes(s.file.size))}</span></span>
        ${busy ? "" : `<button class="btn btn-ghost btn-sm" type="button" data-dk="pick">${icon("refresh")}<span>Choose another file</span></button>`}
      </div>
      ${errors.file ? `<p class="dk-error">${esc(errors.file)}</p>` : ""}` : `
      <div class="dropzone dk-dropzone${locked ? " disabled" : ""}" id="dk-dropzone" role="button" tabindex="0" data-dk="pick" aria-disabled="${locked}">
        <span class="dropzone-icon">${icon("upload")}</span>
        <strong>Drop the project ZIP here</strong>
        <span>or click to choose a file${maxMb ? ` · up to ${esc(maxMb)} MB` : ""}</span>
      </div>`;
    const field = (key, label, hint, value) => `
      <label class="field">
        <span>${esc(label)}</span>
        <input class="input" id="dk-${key}" data-field="${key}" autocomplete="off" spellcheck="false" value="${esc(value)}" ${busy || locked ? "disabled" : ""}>
        <span class="hint${errors[key] && s.touched[key] ? " is-error" : ""}" data-hint="${key}">${esc(errors[key] && s.touched[key] ? errors[key] : hint)}</span>
      </label>`;
    const canStart = !busy && !locked && !Object.keys(errors).length;
    const buttons = busy
      ? `<button class="btn btn-danger" type="button" data-dk="cancel">${icon("stop")}<span>Cancel build</span></button>`
      : s.status === "done"
        ? `<button class="btn btn-primary" type="button" data-dk="again">${icon("plus")}<span>Build another</span></button>`
        : `<button class="btn btn-primary" type="button" id="dk-start" data-dk="start" ${canStart ? "" : "disabled"}>${icon("container")}<span>Build &amp; Push</span></button>`;
    return `
      ${fileChip}
      <ul class="dk-reqs">
        <li>${icon("file")}<span><strong>Dockerfile</strong> at the ZIP root or in a sub-folder</span></li>
        <li>${icon("eyeOff")}<span><strong>.dockerignore</strong> is respected</span></li>
        <li>${icon("book")}<span><strong>README.md</strong> becomes the catalog overview</span></li>
      </ul>
      <div class="dk-fields">
        ${field("image", "Image name", t("bNameHint"), s.image)}
        ${field("tag", "Tag", t("bTagHint"), s.tag)}
        ${field("dockerfile", "Dockerfile path", t("bDockerfileHint"), s.dockerfile)}
      </div>
      <div class="dk-build-bar">
        <div class="dk-target"><span>Target</span><code id="dk-target">${esc(targetRef())}</code></div>
        <div class="dk-build-actions">${buttons}</div>
      </div>`;
  }

  function terminalHtml() {
    const s = b();
    const busy = BUSY.has(s.status);
    const cls = s.status === "error" ? "is-error" : s.status === "done" ? "is-done" : s.status === "cancelled" ? "is-cancelled" : busy ? "is-busy" : "";
    const done = s.status === "done" && s.result;
    const btn = (action, iconName, label, pressed = null) => `<button class="dk-term-btn${pressed ? " is-on" : ""}" type="button" data-dk="${action}" title="${esc(label)}" aria-label="${esc(label)}"${pressed !== null ? ` aria-pressed="${pressed}"` : ""}>${icon(iconName)}</button>`;
    return `
      <div class="dk-term ${cls}${state.wrap ? " is-wrap" : ""}" id="dk-term">
        <div class="dk-term-head">
          <span class="dk-term-dots" aria-hidden="true"><i></i><i></i><i></i></span>
          <span class="dk-term-title">${icon("terminal")}<span>Build log</span></span>
          <span class="dk-term-status" id="dk-term-status" role="status" aria-live="polite">${busy ? '<span class="dk-spinner"></span>' : ""}<span>${esc(statusLine())}</span></span>
          <span class="dk-term-actions">
            ${btn("wrap", "text", "Wrap long lines", state.wrap)}
            ${btn("copy-log", "copy", "Copy log")}
            ${btn("download-log", "download", "Download log")}
            ${busy ? "" : btn("clear", "trash", "Clear")}
          </span>
        </div>
        <div class="dk-upload-bar" ${s.status === "uploading" && s.pct < 100 ? "" : "hidden"}><span id="dk-upload-fill" style="width:${s.pct}%"></span></div>
        <pre class="dk-term-body" id="dk-term-body" tabindex="0" aria-label="Build log output"></pre>
        ${done ? `
        <div class="dk-term-result">
          ${icon("check")}
          <code>docker pull ${esc(s.result.reference)}</code>
          <button class="btn btn-secondary btn-sm" type="button" data-dk="copy-value" data-value="${esc(`docker pull ${s.result.reference}`)}">${icon("copy")}<span>Copy</span></button>
          ${state.config && state.config.catalog ? `<button class="btn btn-primary btn-sm" type="button" data-dk="open-built">${icon("external")}<span>Open in catalog</span></button>` : ""}
        </div>` : ""}
      </div>`;
  }

  function unavailableHtml() {
    const cfg = state.config;
    if (!cfg) {
      return state.configError
        ? emptyState("Could not load the builder settings", state.configError, "alert", `<button class="btn btn-secondary" type="button" data-dk="reload-build">${icon("refresh")}<span>Retry</span></button>`)
        : '<div class="card uploader uploader-loading" aria-hidden="true"></div>';
    }
    const reason = cfg.build && cfg.build.reason;
    if (!cfg.configured || reason === "not_configured") return emptyState("The Docker registry is not configured", t("notConfiguredText"), "container");
    if (reason === "admin_only") return emptyState("Administrators only", "Image builds run on the host Docker engine, so they are restricted to administrators.", "lock");
    if (reason === "disabled") return emptyState("Image builds are disabled", "An administrator turned off the Docker Image Builder in the admin console.", "container");
    return emptyState("The Docker Image Builder is hidden", "An administrator hid this tool in the portal interface settings.", "eyeOff");
  }

  function renderBuildCard() {
    emitHub();
    const root = $("#docker-build-root");
    if (!root) return;
    const access = buildAccess();
    if (!access.show) {
      root.innerHTML = unavailableHtml();
      return;
    }
    let notice = "";
    if (access.reason === "sign_in") {
      notice = `<div class="notice notice-row">${icon("lock")}<span>Sign in to build images.</span><button class="btn btn-secondary btn-sm" type="button" data-action="login">${icon("login")}<span>Sign in</span></button></div>`;
    } else if (access.engine && !access.engine.available) {
      notice = `<div class="notice">${icon("alert")}<span>The Docker engine is unavailable: ${esc(access.engine.error || "")}</span></div>`;
    }
    const s = b();
    const showTerm = s.status !== "idle" || s.lines.length;
    root.innerHTML = `
      ${notice}
      <section class="card dk-build">
        <div id="dk-controls">${access.allowed ? controlsHtml() : ""}</div>
      </section>
      ${showTerm ? `<section class="dk-run"><div id="dk-phases-wrap">${phaseSteps()}</div>${terminalHtml()}</section>` : ""}`;
    if (showTerm) repaintTerminal();
  }

  // Refresh only what changes as the user types, so the focused input keeps its caret.
  function refreshFormState() {
    const errors = formErrors();
    const s = b();
    const target = $("#dk-target");
    if (target) target.textContent = targetRef();
    ["image", "tag", "dockerfile"].forEach((key) => {
      const hint = $(`[data-hint="${key}"]`);
      if (!hint) return;
      const bad = errors[key] && s.touched[key];
      hint.textContent = bad ? errors[key] : t({ image: "bNameHint", tag: "bTagHint", dockerfile: "bDockerfileHint" }[key]);
      hint.classList.toggle("is-error", Boolean(bad));
    });
    const start = $("#dk-start");
    if (start) start.disabled = Boolean(Object.keys(errors).length) || !buildAccess().allowed;
  }

  function lineNode(line) {
    const el = document.createElement("div");
    el.className = `dk-line dk-${line.kind}`;
    if (line.kind === "progress") {
      const pct = line.total ? Math.min(100, Math.round((line.current / line.total) * 100)) : 0;
      el.innerHTML = `<span class="dk-layer-id">${esc(line.id)}</span><span class="dk-layer-status">${esc(line.status)}</span><span class="dk-layer-bar"><span style="width:${pct}%"></span></span><span class="dk-layer-num">${esc(humanBytes(line.current))} / ${esc(humanBytes(line.total))}</span>`;
    } else {
      el.textContent = line.text;
    }
    return el;
  }

  function repaintTerminal() {
    const body = $("#dk-term-body");
    if (!body) return;
    const fragment = document.createDocumentFragment();
    b().lines.forEach((line) => { line.node = lineNode(line); fragment.appendChild(line.node); });
    body.replaceChildren(fragment);
    body.scrollTop = body.scrollHeight;
  }

  function pushLine(line) {
    const s = b();
    const body = $("#dk-term-body");
    const stick = body ? body.scrollHeight - body.scrollTop - body.clientHeight < 40 : false;
    if (line.id && (line.kind === "progress" || line.kind === "layer")) {
      const existing = s.lines.find((l) => l.id === line.id && (l.kind === "progress" || l.kind === "layer"));
      if (existing) {
        Object.assign(existing, line);
        const node = lineNode(existing);
        if (existing.node && existing.node.parentNode) existing.node.replaceWith(node);
        existing.node = node;
        return;
      }
    }
    s.lines.push(line);
    if (s.lines.length > MAX_TERMINAL_LINES) {
      const dropped = s.lines.splice(0, s.lines.length - MAX_TERMINAL_LINES);
      dropped.forEach((l) => l.node && l.node.remove());
    }
    if (body) {
      line.node = lineNode(line);
      body.appendChild(line.node);
      if (stick) body.scrollTop = body.scrollHeight;
    }
  }

  function updateStatus() {
    const status = $("#dk-term-status");
    if (status) status.innerHTML = `${BUSY.has(b().status) ? '<span class="dk-spinner"></span>' : ""}<span>${esc(statusLine())}</span>`;
    const bar = $(".dk-upload-bar");
    if (bar) bar.hidden = b().status !== "uploading" || b().pct >= 100;
    const wrap = $("#dk-phases-wrap");
    if (wrap) wrap.innerHTML = phaseSteps();
    emitHub();
  }

  function logText() {
    return b().lines.map((l) => (l.kind === "progress" ? `${l.id}: ${l.status} ${humanBytes(l.current)}/${humanBytes(l.total)}` : l.text)).join("\n");
  }

  function downloadLog() {
    const s = b();
    const blob = new Blob([`${logText()}\n`], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    a.href = url;
    a.download = `docker-build-${(s.image || "image").replace(/[^a-z0-9._-]+/g, "-")}-${stamp}.log`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function onBuildEvent(kind, data) {
    const s = b();
    switch (kind) {
      case "start":
        s.status = "running";
        pushLine({ kind: "meta", text: `▶ ${data.reference}` });
        break;
      case "step":
        s.status = "running";
        s.phase = data.phase;
        pushLine({ kind: "step", text: `── ${t("phase")[data.phase] || data.phase} ──` });
        updateStatus();
        break;
      case "log":
        pushLine({ kind: /^Step \d+\/\d+|^#\d+ /.test(data.text) ? "stepline" : "log", text: data.text });
        break;
      case "progress":
        pushLine({ kind: "progress", id: data.id, status: data.status, current: data.current, total: data.total });
        break;
      case "layer":
        pushLine({ kind: "layer", id: data.id, text: data.text });
        break;
      case "done":
        s.status = "done";
        s.result = data;
        pushLine({ kind: "ok", text: `✔ ${data.reference}${data.digest ? `  ${data.digest}` : ""}` });
        state.images = null;
        state.details.clear();
        toast(t("bDone", data.seconds), "success", 4000);
        renderBuildCard();
        break;
      case "error":
        s.status = "error";
        s.error = data.message;
        pushLine({ kind: "err", text: `✖ ${data.message}` });
        renderBuildCard();
        break;
      default:
        break;
    }
  }

  function startBuild() {
    const s = b();
    if (Object.keys(formErrors()).length || BUSY.has(s.status)) return;
    Object.assign(s, { status: "uploading", pct: 0, phase: null, error: "", result: null, lines: [], startedAt: Date.now() });
    renderBuildCard();
    const params = new URLSearchParams({ image: s.image, tag: s.tag, dockerfile: s.dockerfile.trim() });
    const xhr = new XMLHttpRequest();
    s.xhr = xhr;
    let offset = 0;
    let buffer = "";
    let finished = false;
    const consume = () => {
      if (xhr.status !== 200) return;
      const chunk = xhr.responseText.slice(offset);
      offset = xhr.responseText.length;
      buffer += chunk;
      let cut;
      while ((cut = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        let event = "message";
        let data = "";
        block.split("\n").forEach((line) => {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data += line.slice(5).trimStart();
        });
        if (!data) continue;
        let payload;
        try { payload = JSON.parse(data); } catch (_) { continue; }
        if (event === "done" || event === "error") finished = true;
        onBuildEvent(event, payload);
      }
    };
    xhr.open("POST", `${API.build}?${params}`);
    xhr.setRequestHeader("X-PAKAL-Request", "1");
    xhr.setRequestHeader("Content-Type", "application/zip");
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      s.pct = Math.min(100, Math.round((e.loaded / e.total) * 100));
      const fill = $("#dk-upload-fill");
      if (fill) fill.style.width = `${s.pct}%`;
      updateStatus();
    };
    xhr.upload.onload = () => {
      s.pct = 100;
      updateStatus();
    };
    xhr.onprogress = consume;
    xhr.onload = () => {
      s.xhr = null;
      if (xhr.status !== 200) {
        let detail = `${xhr.status} ${xhr.statusText}`;
        try {
          const body = JSON.parse(xhr.responseText);
          if (body && typeof body.detail === "string") detail = body.detail;
          else if (body && Array.isArray(body.detail) && body.detail[0]) detail = body.detail[0].msg;
        } catch (_) { /* not JSON */ }
        s.status = "error";
        s.error = detail;
        pushLine({ kind: "err", text: `✖ ${detail}` });
        renderBuildCard();
        return;
      }
      consume();
      if (!finished) {
        s.status = "error";
        s.error = t("bStreamEnded");
        pushLine({ kind: "err", text: `✖ ${t("bStreamEnded")}` });
        renderBuildCard();
      }
    };
    xhr.onerror = () => {
      s.xhr = null;
      if (finished) return;
      s.status = "error";
      s.error = t("bNetwork");
      pushLine({ kind: "err", text: `✖ ${t("bNetwork")}` });
      renderBuildCard();
    };
    xhr.onabort = () => {
      s.xhr = null;
      s.status = "cancelled";
      pushLine({ kind: "err", text: `■ ${t("bCancelled")}` });
      renderBuildCard();
    };
    xhr.send(s.file);
  }

  function setFile(file) {
    if (!file || BUSY.has(b().status)) return;
    const access = buildAccess();
    if (!access.allowed || (access.engine && !access.engine.available)) return;
    const s = b();
    s.file = file;
    if (s.status !== "idle") Object.assign(s, { status: "idle", phase: null, error: "", result: null });
    suggestFromFile(file);
    renderBuildCard();
    if (formErrors().file) toast(formErrors().file, "error");
  }

  // ------------------------------------------------------------------ events

  function handle(el, event) {
    switch (el.dataset.dk) {
      case "open":
        openImage(el.dataset.name);
        break;
      case "tab":
        if (state.modal && MODAL_TABS.includes(el.dataset.tab)) {
          state.modal.tab = el.dataset.tab;
          renderModal();
          const active = $(".dk-tab.active");
          if (active) active.focus();
        }
        break;
      case "view-tag":
        selectTag(el.dataset.tag, "overview");
        break;
      case "refresh":
        loadImages({ fresh: true });
        break;
      case "reload":
        loadConfig().then(() => { if (state.config && state.config.catalog) loadImages(); else renderCatalog(); });
        break;
      case "reload-build":
        loadConfig();
        break;
      case "copy-value":
        copyText(el.dataset.value);
        break;
      case "copy-code": {
        const code = el.closest(".dk-codeblock");
        if (code) copyText($("code", code).textContent);
        break;
      }
      case "copy-log":
        copyText(logText());
        break;
      case "download-log":
        downloadLog();
        break;
      case "wrap": {
        state.wrap = !state.wrap;
        const term = $("#dk-term");
        if (term) term.classList.toggle("is-wrap", state.wrap);
        el.classList.toggle("is-on", state.wrap);
        el.setAttribute("aria-pressed", String(state.wrap));
        break;
      }
      case "pick":
        if (el.getAttribute("aria-disabled") === "true") return;
        $("#docker-zip-input").click();
        break;
      case "start":
        startBuild();
        break;
      case "cancel":
        if (b().xhr) b().xhr.abort();
        break;
      case "again":
        state.build = newBuild({ tag: b().tag, dockerfile: b().dockerfile });
        renderBuildCard();
        break;
      case "clear":
        b().lines = [];
        if (!BUSY.has(b().status)) Object.assign(b(), { status: "idle", phase: null, error: "", result: null });
        renderBuildCard();
        break;
      case "open-built": {
        const result = b().result;
        if (!result) return;
        window.location.hash = "#docker";
        openImage(result.repository, result.tag);
        break;
      }
      default:
        return;
    }
    if (event) event.preventDefault();
  }

  function bind() {
    document.addEventListener("click", (event) => {
      const el = event.target instanceof Element ? event.target.closest("[data-dk]") : null;
      if (el && !el.disabled) handle(el, event);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && state.modal) {
        event.stopPropagation();
        closeImage();
        return;
      }
      const target = event.target;
      if (state.modal && target instanceof Element && target.matches(".dk-tab") && (event.key === "ArrowRight" || event.key === "ArrowLeft")) {
        event.preventDefault();
        const index = MODAL_TABS.indexOf(state.modal.tab);
        const next = MODAL_TABS[(index + (event.key === "ArrowRight" ? 1 : MODAL_TABS.length - 1)) % MODAL_TABS.length];
        handle({ dataset: { dk: "tab", tab: next } }, null);
        return;
      }
      if ((event.key === "Enter" || event.key === " ") && target instanceof Element && target.matches("[data-dk][role='button']")) {
        event.preventDefault();
        handle(target, null);
      }
    }, true);
    document.addEventListener("input", (event) => {
      const target = event.target;
      if (target.id === "dk-search") {
        state.search = target.value;
        renderCatalog();
        return;
      }
      if (target.dataset && target.dataset.field && target.closest("#docker-build-root")) {
        const key = target.dataset.field;
        b()[key] = key === "image" ? target.value.trim().toLowerCase() : target.value.trim();
        b().touched[key] = true;
        refreshFormState();
      }
    });
    document.addEventListener("change", (event) => {
      if (event.target.id === "dk-tag" && state.modal) selectTag(event.target.value);
    });
    $("#docker-zip-input").addEventListener("change", (event) => {
      const file = event.target.files && event.target.files[0];
      event.target.value = "";
      setFile(file);
    });
    $("#docker-modal-close").addEventListener("click", closeImage);
    $("#docker-modal").addEventListener("click", (event) => { if (event.target.id === "docker-modal") closeImage(); });

    const root = $("#docker-build-root");
    const hasFiles = (e) => Boolean(e.dataTransfer) && Array.from(e.dataTransfer.types || []).includes("Files");
    let depth = 0;
    const zone = () => $("#dk-dropzone");
    root.addEventListener("dragenter", (e) => {
      if (!hasFiles(e) || !zone()) return;
      e.preventDefault();
      depth += 1;
      zone().classList.add("dragging");
    });
    root.addEventListener("dragover", (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = zone() && !zone().classList.contains("disabled") ? "copy" : "none";
    });
    root.addEventListener("dragleave", () => {
      depth = Math.max(0, depth - 1);
      if (!depth && zone()) zone().classList.remove("dragging");
    });
    root.addEventListener("drop", (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      depth = 0;
      if (zone()) zone().classList.remove("dragging");
      const files = Array.from(e.dataTransfer.files || []);
      if (files.length) setFile(files.find((f) => /\.zip$/i.test(f.name)) || files[0]);
    });

    window.addEventListener("beforeunload", (e) => {
      if (!BUSY.has(b().status)) return;
      e.preventDefault();
      e.returnValue = t("bLeave");
    });

    // A ZIP dropped on the hub card: the config may still be loading, so apply it once it is known.
    document.addEventListener("pakal:docker-file", (e) => {
      const file = e.detail;
      (state.config ? Promise.resolve() : loadConfig()).then(() => setFile(file));
    });
    document.addEventListener("pakal:view", (e) => {
      state.view = e.detail;
      if (state.view === "docker") {
        const ready = state.config ? Promise.resolve() : loadConfig();
        ready.then(() => {
          renderCatalog();
          if (state.config && state.config.catalog && !state.images && !state.imagesLoading) loadImages();
        });
        renderCatalog();
      } else if (state.view === "actions" && !BUSY.has(b().status)) {
        loadConfig();
      }
      if (state.view !== "docker" && state.modal) closeImage();
    });
    document.addEventListener("pakal:actions-tool", (e) => {
      state.tool = e.detail;
      if (state.tool === "docker") renderBuildCard();
    });
    // Sign-in, sign-out and visibility changes alter who may build and what is shown.
    const refresh = () => {
      if (BUSY.has(b().status)) return;
      if (state.view === "actions" || state.view === "docker") loadConfig().then(renderCatalog);
      else state.config = null;
    };
    const identity = (auth) => JSON.stringify([auth && auth.user && auth.user.username, Boolean(auth && auth.admin && auth.admin.allowed)]);
    document.addEventListener("pakal:auth", (e) => {
      const before = identity(state.auth);
      state.auth = e.detail;
      if (before !== identity(state.auth)) refresh();
    });
    document.addEventListener("pakal:ui", refresh);
  }

  bind();
})();

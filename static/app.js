const TARGET_CANDIDATES = [
  { code: "fr", label: "French (FR)" },
  { code: "de", label: "German (DE)" },
  { code: "es", label: "Spanish (ES)" },
  { code: "uk", label: "Ukrainian (UA)" },
  { code: "ga", label: "Irish (IE)" },
];
const selectedTargets = new Set(["fr", "de", "uk"]);

async function checkHealth() {
  const badge = document.getElementById("healthBadge");
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    const parts = [];
    parts.push(data.translator_configured ? "Translator: configured" : "Translator: NOT configured (set TRANSLATOR_KEY/REGION)");
    parts.push(data.foundry_configured ? "Foundry: configured" : "Foundry: not configured");
    badge.textContent = parts.join(" · ");
    badge.className = "badge " + (data.translator_configured ? "ok" : "err");
  } catch (e) {
    badge.textContent = "Could not reach API";
    badge.className = "badge err";
  }
}

function renderTargetChips() {
  const container = document.getElementById("targetLangs");
  container.innerHTML = "";
  TARGET_CANDIDATES.forEach((lang) => {
    const chip = document.createElement("div");
    chip.className = "chip" + (selectedTargets.has(lang.code) ? " selected" : "");
    chip.textContent = lang.label;
    chip.onclick = () => {
      if (selectedTargets.has(lang.code)) selectedTargets.delete(lang.code);
      else selectedTargets.add(lang.code);
      renderTargetChips();
    };
    container.appendChild(chip);
  });
}

async function loadLanguages() {
  try {
    const res = await fetch("/api/languages");
    if (!res.ok) throw new Error("languages fetch failed");
    const data = await res.json();
    const sourceSelect = document.getElementById("sourceLang");
    const translitLang = document.getElementById("translitLang");
    Object.values(data.translation)
      .sort((a, b) => a.name.localeCompare(b.name))
      .forEach((lang) => {
        const opt = document.createElement("option");
        opt.value = lang.code;
        opt.textContent = `${lang.name} (${lang.code})`;
        sourceSelect.appendChild(opt);
      });

    const translitCodes = Object.keys(data.transliteration || {});
    translitCodes.forEach((code) => {
      const opt = document.createElement("option");
      opt.value = code;
      opt.textContent = code;
      if (code === "uk") opt.selected = true;
      translitLang.appendChild(opt);
    });
    populateScripts(data.transliteration, translitLang.value || translitCodes[0]);
    translitLang.onchange = () => populateScripts(data.transliteration, translitLang.value);
  } catch (e) {
    console.error(e);
  }
}

function populateScripts(transliterationMap, langCode) {
  const fromSel = document.getElementById("fromScript");
  const toSel = document.getElementById("toScript");
  fromSel.innerHTML = "";
  toSel.innerHTML = "";
  const info = transliterationMap && transliterationMap[langCode];
  const scripts = info ? (info.scripts || []).map((s) => s.code) : ["Cyrl", "Latn"];
  scripts.forEach((s) => {
    fromSel.appendChild(new Option(s, s));
    toSel.appendChild(new Option(s, s));
  });
  if (scripts.includes("Cyrl")) fromSel.value = "Cyrl";
  if (scripts.includes("Latn")) toSel.value = "Latn";
}

function parseDynamicDictionary(raw) {
  const dict = {};
  raw
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .forEach((line) => {
      const idx = line.indexOf("=");
      if (idx > 0) {
        const key = line.slice(0, idx).trim();
        const val = line.slice(idx + 1).trim();
        if (key && val) dict[key] = val;
      }
    });
  return Object.keys(dict).length ? dict : null;
}

async function doTranslate() {
  const resultBox = document.getElementById("translateResult");
  resultBox.innerHTML = "Translating…";

  const text = document.getElementById("text").value;
  const sourceLanguage = document.getElementById("sourceLang").value || null;
  const targets = Array.from(selectedTargets);
  if (!targets.length) {
    resultBox.innerHTML = '<div class="error-box">Select at least one target language.</div>';
    return;
  }

  const noTranslateRaw = document.getElementById("noTranslate").value.trim();
  const noTranslateTerms = noTranslateRaw ? noTranslateRaw.split(",").map((t) => t.trim()).filter(Boolean) : null;
  const dynamicDictionary = parseDynamicDictionary(document.getElementById("dynamicDict").value);

  const engine = document.getElementById("engine").value;
  const tone = document.getElementById("tone").value || null;
  const gender = document.getElementById("gender").value || null;

  const body = {
    text,
    target_languages: targets,
    source_language: sourceLanguage,
    profanity_action: document.getElementById("profanityAction").value,
    no_translate_terms: noTranslateTerms,
    dynamic_dictionary: dynamicDictionary,
    use_llm: engine === "llm",
    tone: engine === "llm" ? tone : null,
    gender: engine === "llm" ? gender : null,
  };

  try {
    const res = await fetch("/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      resultBox.innerHTML = `<div class="error-box">${data.detail || "Translation failed"}</div>`;
      return;
    }

    let html = "";
    if (data.detected_language) {
      html += `<div class="result-meta">Detected source language: <b>${data.detected_language.language}</b> (confidence ${(data.detected_language.score * 100).toFixed(0)}%)</div>`;
    }
    html += `<div class="result-meta">Engine: <b>${data.engine.toUpperCase()}</b></div>`;
    for (const [lang, translated] of Object.entries(data.translations)) {
      html += `<div class="result-item"><div class="lang">${lang}</div>${translated}</div>`;
    }
    (data.warnings || []).forEach((w) => {
      html += `<div class="warn">⚠ ${w}</div>`;
    });
    resultBox.innerHTML = html;
  } catch (e) {
    resultBox.innerHTML = `<div class="error-box">Request failed: ${e}</div>`;
  }
}

async function doTransliterate() {
  const resultBox = document.getElementById("translitResult");
  resultBox.innerHTML = "Converting…";
  const body = {
    text: document.getElementById("translitText").value,
    language: document.getElementById("translitLang").value,
    from_script: document.getElementById("fromScript").value,
    to_script: document.getElementById("toScript").value,
  };
  try {
    const res = await fetch("/api/transliterate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      resultBox.innerHTML = `<div class="error-box">${data.detail || "Transliteration failed"}</div>`;
      return;
    }
    resultBox.innerHTML = `<div class="result-item">${data.text}</div>`;
  } catch (e) {
    resultBox.innerHTML = `<div class="error-box">Request failed: ${e}</div>`;
  }
}

document.getElementById("translateBtn").addEventListener("click", doTranslate);
document.getElementById("translitBtn").addEventListener("click", doTransliterate);

renderTargetChips();
checkHealth();
loadLanguages();

const TOPIC_ORDER = [
  "Generative AI",
  "Human–AI Interaction",
  "Digital Platforms",
  "Platform Governance",
  "Open Source Software",
  "Digital Labor",
  "Digital Innovation",
  "Entrepreneurship",
  "Information Economics",
  "Human–AI Collaboration",
  "AI Agent",
  "Decision Making",
  "Information Ecosystems",
  "Platform Economy",
  "AI Agent Collaboration",
  "AI Agent Information Systems",
  "Crowdsourcing",
  "Online Communities",
  "Social Networks",
  "Digital Healthcare",
  "Online Platforms",
  "Online Markets / E-Commerce",
  "Crowdfunding",
  "Sharing / Gig Economy",
  "Online Knowledge Sharing"];
const state = { papers: [], filtered: [], view: "main", saved: new Map(), selectedTopics: new Set(), selectedMethods: new Set(), activePaper: null };
const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];

function escapeHtml(value = "") { const node = document.createElement("div"); node.textContent = value; return node.innerHTML; }
function stableId(paper) { return paper.doi || paper.id; }
function formatDate(value) { return value ? new Date(`${value}T00:00:00`).toLocaleDateString("ko-KR", { year: "numeric", month: "short", day: "numeric" }) : "날짜 미상"; }
function isNew(paper) {return paper.is_new === true;}
function bookmarkSvg() { return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 4.5A1.5 1.5 0 0 1 8 3h8a1.5 1.5 0 0 1 1.5 1.5V21L12 17.6 6.5 21V4.5Z"/></svg>`; }
function tags(paper) {
  const topics = (paper.topics || []).map(tag => `<span class="tag topic" title="Research Topic">#${escapeHtml(tag.replaceAll(" ", "-"))}</span>`).join("");
  const methods = (paper.methods || []).map(tag => `<span class="tag method" title="Methodology">#${escapeHtml(tag.replaceAll(" ", "-"))}</span>`).join("");
  return topics + methods;
}

function loadSaved() {
  try {
    const stored = JSON.parse(localStorage.getItem("paperRadarSavedPapers") || "[]");
    state.saved = new Map(stored.filter(paper => paper && (paper.doi || paper.id)).map(paper => [stableId(paper), paper]));
  } catch { state.saved = new Map(); }
}
function persistSaved() {
  localStorage.setItem("paperRadarSavedPapers", JSON.stringify([...state.saved.values()]));
  $("#saved-count").textContent = state.saved.size;
}
function toggleSaved(id) {
  const paper = state.papers.find(item => stableId(item) === id) || state.saved.get(id) || state.activePaper;
  state.saved.has(id) ? state.saved.delete(id) : state.saved.set(id, paper);
  persistSaved(); applyFilters();
  if (state.activePaper && stableId(state.activePaper) === id) updateDialogBookmark();
}

function buildChecks(container, values, type) {
  container.innerHTML = values.map((value, index) => `<label class="check-option"><input type="checkbox" value="${escapeHtml(value)}" data-filter-type="${type}"><span class="custom-check"></span><span>${escapeHtml(value)}</span></label>`).join("");
}
function updateFilterLabels() {
  $("#topic-selected").textContent = state.selectedTopics.size ? `${state.selectedTopics.size}개 선택` : "선택 없음";
  $("#method-selected").textContent = state.selectedMethods.size ? `${state.selectedMethods.size}개 선택` : "선택 없음";
  const chips = [...state.selectedTopics].map(value => `<button class="filter-chip topic" data-remove-topic="${escapeHtml(value)}">${escapeHtml(value)} ×</button>`)
    .concat([...state.selectedMethods].map(value => `<button class="filter-chip method" data-remove-method="${escapeHtml(value)}">${escapeHtml(value)} ×</button>`));
  $("#active-filters").innerHTML = chips.join("");
}

function render() {
  $("#paper-list").innerHTML = state.filtered.map(paper => {
    const id = stableId(paper); const saved = state.saved.has(id);
    return `<article class="paper" data-paper-id="${escapeHtml(id)}" tabindex="0">
      <div class="paper-meta"><span class="journal">${escapeHtml(paper.journal_short || paper.journal)}</span><p>${formatDate(paper.publication_date)}</p>${isNew(paper) ? '<span class="new-badge">NEW</span>' : ""}</div>
      <div class="paper-body"><h2>${escapeHtml(paper.title)}</h2><p class="authors">${escapeHtml((paper.authors || []).join(", "))}</p><div class="tags">${tags(paper)}</div><p class="first-seen">페이퍼 토벌 등록일 · ${formatDate(paper.first_seen_at)}</p></div>
      <button class="bookmark ${saved ? "saved" : ""}" type="button" data-bookmark-id="${escapeHtml(id)}" aria-label="${saved ? "저장 해제" : "논문 저장"}" aria-pressed="${saved}">${bookmarkSvg()}</button>
    </article>`;
  }).join("");
  $("#paper-count").textContent = state.filtered.length;
  const empty = state.filtered.length === 0; $("#empty").hidden = !empty;
  if (empty && state.view === "saved" && state.saved.size === 0) {
    $("#empty-title").textContent = "아직 저장한 논문이 없습니다.";
    $("#empty-help").textContent = "관심 있는 논문의 책갈피를 눌러 보관해보세요.";
    $("#empty-action").textContent = "Main으로 이동";
  } else if (empty) {
    $("#empty-title").textContent = "조건에 맞는 논문이 없습니다.";
    $("#empty-help").textContent = "필터를 변경해 다시 확인해보세요.";
    $("#empty-action").textContent = "필터 초기화";
  }
  updateFilterLabels();
}

function applyFilters() {
  const query = $("#search").value.trim().toLowerCase(); const journal = $("#journal-filter").value;
  const source = state.view === "saved" ? [...state.saved.values()] : state.papers;
  let papers = source.filter(paper => {
    const haystack = [paper.title, paper.abstract, ...(paper.authors || []), ...(paper.methods || []), ...(paper.topics || [])].join(" ").toLowerCase();
    return (!query || haystack.includes(query)) && (!journal || paper.journal === journal)
      && (!state.selectedTopics.size || (paper.topics || []).some(t => state.selectedTopics.has(t)))
      && (!state.selectedMethods.size || (paper.methods || []).some(m => state.selectedMethods.has(m)));
  });
  const key = $("#sort").value === "first_seen" ? "first_seen_at" : "publication_date";
  papers.sort((a, b) => (b[key] || "").localeCompare(a[key] || "")); state.filtered = papers; render();
}

function switchView(view) {
  state.view = view;

  $$(".nav-link[data-view]").forEach(button => {
    button.classList.toggle(
      "active",
      button.dataset.view === view
    );
  });

  history.replaceState(null, "", `#${view}`);
  applyFilters();
}

function updateDialogBookmark() {
  const id = stableId(state.activePaper); const saved = state.saved.has(id); const button = $("#dialog-bookmark");
  button.classList.toggle("saved", saved); button.setAttribute("aria-pressed", String(saved)); button.setAttribute("aria-label", saved ? "저장 해제" : "논문 저장"); button.innerHTML = bookmarkSvg();
}
function openPaper(paper) {
  state.activePaper = paper;
  $("#dialog-content").innerHTML = `<div class="dialog-meta"><span>${escapeHtml(paper.journal)}</span><span>${formatDate(paper.publication_date)}</span></div>
    <h2>${escapeHtml(paper.title)}</h2><p class="dialog-authors">${escapeHtml((paper.authors || []).join(", "))}</p><div class="tags dialog-tags">${tags(paper)}</div>
    <dl class="dates"><div><dt>Paper Radar 등록일</dt><dd>${formatDate(paper.first_seen_at)}</dd></div>${paper.doi ? `<div><dt>DOI</dt><dd>${escapeHtml(paper.doi)}</dd></div>` : ""}</dl>
    <section class="abstract-full"><h3>Abstract</h3><p>${escapeHtml(paper.abstract || "초록이 제공되지 않았습니다.")}</p></section>
    <div class="dialog-actions">${paper.doi_url ? `<a href="${escapeHtml(paper.doi_url)}" target="_blank" rel="noreferrer">DOI 페이지 ↗</a>` : ""}<a href="${escapeHtml(paper.journal_url || paper.url)}" target="_blank" rel="noreferrer">저널 원문 ↗</a></div>`;
  updateDialogBookmark(); $("#paper-dialog").showModal();
}

function resetFilters() {
  $("#search").value = ""; $("#journal-filter").value = ""; $("#sort").value = "publication"; state.selectedTopics.clear(); state.selectedMethods.clear();
  $$("input[data-filter-type]").forEach(input => { input.checked = false; }); applyFilters();
}

async function init() {
  loadSaved(); persistSaved();
  try {
    const response = await fetch(`data/papers.json?v=${Date.now()}`); if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json(); state.papers = payload.papers || [];
    [...new Set(state.papers.map(p => p.journal))].sort().forEach(value => $("#journal-filter").insertAdjacentHTML("beforeend", `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`));
    buildChecks($("#topic-options"), TOPIC_ORDER.filter(t => state.papers.some(p => (p.topics || []).includes(t))), "topic");
    buildChecks($("#method-options"), [...new Set(state.papers.flatMap(p => p.methods || []))].sort(), "method");
    $("#updated").textContent = `마지막 업데이트 ${payload.updated_at ? new Date(payload.updated_at).toLocaleString("ko-KR", { dateStyle: "medium", timeStyle: "short" }) : "정보 없음"}`;
    switchView(location.hash === "#saved" ? "saved" : "main");
  } catch (error) { $("#updated").textContent = "데이터를 불러오지 못했습니다"; $("#paper-list").innerHTML = `<div class="empty"><p>논문 데이터를 불러오지 못했습니다.</p></div>`; console.error(error); }
}

$("#search").addEventListener("input", applyFilters); $("#journal-filter").addEventListener("change", applyFilters); $("#sort").addEventListener("change", applyFilters); $("#reset").addEventListener("click", resetFilters);
$$(".nav-link[data-view]").forEach(button => button.addEventListener("click", () => switchView(button.dataset.view)));
$(".toolbar").addEventListener("change", event => { const input = event.target.closest("input[data-filter-type]"); if (!input) return; const set = input.dataset.filterType === "topic" ? state.selectedTopics : state.selectedMethods; input.checked ? set.add(input.value) : set.delete(input.value); applyFilters(); });
$("#active-filters").addEventListener("click", event => { const button = event.target.closest("button"); if (!button) return; const value = button.dataset.removeTopic || button.dataset.removeMethod; const set = button.dataset.removeTopic ? state.selectedTopics : state.selectedMethods; set.delete(value); const input = $(`input[data-filter-type][value="${CSS.escape(value)}"]`); if (input) input.checked = false; applyFilters(); });
$("#paper-list").addEventListener("click", event => { const bookmark = event.target.closest("[data-bookmark-id]"); if (bookmark) { event.stopPropagation(); toggleSaved(bookmark.dataset.bookmarkId); return; } const card = event.target.closest("[data-paper-id]"); if (card) openPaper(state.papers.find(p => stableId(p) === card.dataset.paperId) || state.saved.get(card.dataset.paperId)); });
$("#paper-list").addEventListener("keydown", event => { if ((event.key === "Enter" || event.key === " ") && event.target.matches("[data-paper-id]")) { const id = event.target.dataset.paperId; openPaper(state.papers.find(p => stableId(p) === id) || state.saved.get(id)); } });
$("#dialog-close").addEventListener("click", () => $("#paper-dialog").close()); $("#paper-dialog").addEventListener("click", event => { if (event.target === $("#paper-dialog")) $("#paper-dialog").close(); });
$("#dialog-bookmark").addEventListener("click", () => toggleSaved(stableId(state.activePaper)));
$("#empty-action").addEventListener("click", () => { if (state.view === "saved" && state.saved.size === 0) switchView("main"); else resetFilters(); });
init();

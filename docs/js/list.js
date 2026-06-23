// list.html — 자격증 목록 검색 & 필터
(function () {
  const grid = document.getElementById("examGrid");
  const metaEl = document.getElementById("listMeta");
  const noResults = document.getElementById("noResults");
  const searchInput = document.getElementById("searchInput");
  const seriesFilter = document.getElementById("seriesFilter");
  const fieldFilter = document.getElementById("fieldFilter");

  let allExams = [];
  let activeSeries = "";
  let activeField = "";

  // URL 파라미터에서 초기 검색어/카테고리 읽기
  const params = new URLSearchParams(location.search);
  const initQ = params.get("q") || "";
  const initCat = params.get("cat") || "";

  function renderGrid(items) {
    if (items.length === 0) {
      grid.innerHTML = "";
      noResults.style.display = "";
      metaEl.textContent = "검색 결과가 없습니다.";
      return;
    }
    noResults.style.display = "none";
    metaEl.textContent = `총 ${items.length}개 자격증`;
    grid.innerHTML = items
      .map(
        (e) => `
      <a href="/exam/${encodeURIComponent(e.name)}.html" class="exam-card">
        <div class="exam-card-name">${e.name}</div>
        <div class="exam-card-meta">
          <span class="cat-badge cat-${e.field_class}" style="font-size:0.75rem;padding:2px 8px;">${e.field}</span>
          <span style="margin-left:6px;font-size:0.8125rem;color:var(--text-secondary);">${e.series}</span>
        </div>
      </a>`
      )
      .join("");
  }

  function filter() {
    const q = searchInput.value.trim();
    const filtered = allExams.filter((e) => {
      const matchQ = !q || e.name.includes(q) || e.field.includes(q);
      const matchSeries = !activeSeries || e.series.includes(activeSeries);
      const matchField = !activeField || e.field.includes(activeField);
      return matchQ && matchSeries && matchField;
    });
    renderGrid(filtered);
  }

  // 직무분야 CSS 클래스
  const FIELD_CSS = {
    "전기·전자": "electric", "전기전자": "electric",
    "정보통신": "it", "IT": "it",
    "건설": "construction",
    "안전관리": "safety", "안전": "safety",
    "기계": "machine",
    "화학": "chem",
    "농림어업": "agri",
    "서비스": "service",
  };

  function getFieldClass(field) {
    for (const [key, cls] of Object.entries(FIELD_CSS)) {
      if (field.includes(key)) return cls;
    }
    return "default";
  }

  function buildFieldButtons(exams) {
    const fields = [...new Set(exams.map((e) => e.field))].sort();
    fieldFilter.innerHTML = `<button class="filter-btn ${!initCat ? "active" : ""}" data-field="">전체 분야</button>`;
    fields.forEach((f) => {
      const btn = document.createElement("button");
      btn.className = "filter-btn" + (f.includes(initCat) && initCat ? " active" : "");
      btn.dataset.field = f;
      btn.textContent = f;
      fieldFilter.appendChild(btn);
    });
  }

  // 데이터 로드
  fetch("/data/exams.json")
    .then((r) => r.json())
    .then((data) => {
      allExams = (data.items || []).map((e) => ({
        ...e,
        field_class: getFieldClass(e.field || ""),
      }));

      buildFieldButtons(allExams);

      if (initQ) searchInput.value = initQ;
      if (initCat) activeField = initCat;

      filter();
    })
    .catch(() => {
      metaEl.textContent = "데이터를 불러오지 못했습니다.";
    });

  // 검색
  searchInput.addEventListener("input", filter);

  // 등급 필터
  seriesFilter.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-series]");
    if (!btn) return;
    activeSeries = btn.dataset.series;
    seriesFilter.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    filter();
  });

  // 분야 필터
  fieldFilter.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-field]");
    if (!btn) return;
    activeField = btn.dataset.field;
    fieldFilter.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    filter();
  });
})();

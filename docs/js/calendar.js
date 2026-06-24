// calendar.html — 월별 시험 캘린더
function examPath(name) { return encodeURIComponent(name).replace(/%28/g,'(').replace(/%29/g,')'); }
(function () {
  const grid = document.getElementById("calGrid");
  const calTitle = document.getElementById("calTitle");
  const listTitle = document.getElementById("listTitle");
  const calList = document.getElementById("calList");
  const seriesFilter = document.getElementById("seriesFilter");

  const DOW = ["일", "월", "화", "수", "목", "금", "토"];
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  let curYear = today.getFullYear();
  let curMonth = today.getMonth(); // 0-indexed
  let activeSeries = "";
  let allEvents = []; // {date, name, event, cls, series, jmcd}

  // 이벤트 타입 → CSS 클래스
  const EVENT_CLS = {
    "필기 원서접수": "ev-reg",
    "필기 시험":     "ev-exam",
    "필기 합격발표": "ev-exam",
    "실기 원서접수": "ev-prac",
    "실기 시험":     "ev-prac",
    "최종 합격발표": "ev-pass",
    "실기 합격발표": "ev-pass",
  };

  // 날짜 범위를 개별 날짜로 확장
  function expandRange(startStr, endStr, name, eventLabel, cls, series, jmcd) {
    if (!startStr) return [];
    const start = new Date(startStr);
    const end = endStr ? new Date(endStr) : start;
    const events = [];
    const cur = new Date(start);
    while (cur <= end) {
      events.push({
        date: cur.toISOString().slice(0, 10),
        name,
        event: eventLabel,
        cls,
        series,
        jmcd,
      });
      cur.setDate(cur.getDate() + 1);
    }
    return events;
  }

  // schedules.json (그룹 일정) + 개별 exam 페이지 내 데이터 로드
  function loadEvents(schedules, exams) {
    const events = [];
    const examMap = {};
    (exams.items || []).forEach((e) => { examMap[e.name] = e; });

    // schedules.json 기반 (그룹 수준)
    (schedules.items || []).forEach((s) => {
      const name = s.name;
      const series = examMap[name]?.series || "";
      const jmcd = examMap[name]?.jmcd || "";

      const pairs = [
        [s.written_reg_start, s.written_reg_end, "필기 원서접수"],
        [s.written_exam_start, s.written_exam_end, "필기 시험"],
        [s.written_pass, s.written_pass, "필기 합격발표"],
        [s.prac_reg_start, s.prac_reg_end, "실기 원서접수"],
        [s.prac_exam_start, s.prac_exam_end, "실기 시험"],
        [s.prac_pass_end, s.prac_pass_end, "최종 합격발표"],
      ];
      pairs.forEach(([start, end, label]) => {
        const cls = EVENT_CLS[label] || "ev-exam";
        events.push(...expandRange(start, end, name, label, cls, series, jmcd));
      });
    });

    return events;
  }

  function renderCalendar() {
    const year = curYear;
    const month = curMonth;
    calTitle.textContent = `${year}년 ${month + 1}월`;
    listTitle.textContent = `${month + 1}월 일정 목록`;

    // 이달 첫날/마지막날
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startDow = firstDay.getDay(); // 0=일

    // 이벤트 필터링 (이달 + 시리즈)
    const monthStr = `${year}-${String(month + 1).padStart(2, "0")}`;
    const filtered = allEvents.filter((e) => {
      const inMonth = e.date.startsWith(monthStr);
      const matchSeries = !activeSeries || e.series === activeSeries;
      return inMonth && matchSeries;
    });

    // 날짜별 이벤트 맵
    const eventMap = {};
    filtered.forEach((e) => {
      (eventMap[e.date] = eventMap[e.date] || []).push(e);
    });

    // 그리드 재생성 (요일 헤더 유지)
    // 기존 날짜 셀 제거
    while (grid.children.length > 7) grid.removeChild(grid.lastChild);

    // 앞쪽 빈 칸
    for (let i = 0; i < startDow; i++) {
      const cell = document.createElement("div");
      cell.className = "cal-day other-month";
      grid.appendChild(cell);
    }

    // 날짜 셀
    for (let d = 1; d <= lastDay.getDate(); d++) {
      const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      const cell = document.createElement("div");
      const isToday = dateStr === today.toISOString().slice(0, 10);
      cell.className = "cal-day" + (isToday ? " today" : "");

      const numEl = document.createElement("div");
      numEl.className = "cal-day-num";
      numEl.textContent = d;
      cell.appendChild(numEl);

      const dayEvents = eventMap[dateStr] || [];
      // 최대 3개만 표시
      dayEvents.slice(0, 3).forEach((ev) => {
        const tag = document.createElement("span");
        tag.className = `cal-event ${ev.cls}`;
        tag.textContent = ev.name ? `${ev.name} ${ev.event}` : ev.event;
        tag.title = `${ev.name} — ${ev.event}`;
        cell.appendChild(tag);
      });
      if (dayEvents.length > 3) {
        const more = document.createElement("span");
        more.style.cssText = "font-size:0.6875rem;color:var(--text-secondary);";
        more.textContent = `+${dayEvents.length - 3}개`;
        cell.appendChild(more);
      }

      grid.appendChild(cell);
    }

    // 뒤쪽 빈 칸 (6주 맞춤)
    const totalCells = startDow + lastDay.getDate();
    const remainder = totalCells % 7;
    if (remainder > 0) {
      for (let i = 0; i < 7 - remainder; i++) {
        const cell = document.createElement("div");
        cell.className = "cal-day other-month";
        grid.appendChild(cell);
      }
    }

    // 목록 렌더링
    const sorted = [...filtered].sort((a, b) => a.date.localeCompare(b.date));
    const uniqueDates = [...new Set(sorted.map((e) => e.date))];

    if (sorted.length === 0) {
      calList.innerHTML = '<p style="color:var(--text-secondary);padding:20px 0;">이달 등록된 일정이 없습니다.</p>';
      return;
    }

    calList.innerHTML = sorted
      .map((ev) => {
        const link = ev.jmcd
          ? `/exam/${examPath(ev.name)}.html`
          : "#";
        return `
        <div class="cal-list-item">
          <div class="cal-list-date">${ev.date.slice(5)}</div>
          <div>
            <a href="${link}" class="cal-list-name" style="color:var(--text-primary);text-decoration:none;">${ev.name}</a>
            <div class="cal-list-event">${ev.event}${ev.series ? " · " + ev.series : ""}</div>
          </div>
        </div>`;
      })
      .join("");
  }

  // 데이터 로드
  Promise.all([
    fetch("/data/schedules.json").then((r) => r.json()).catch(() => ({ items: [] })),
    fetch("/data/exams.json").then((r) => r.json()).catch(() => ({ items: [] })),
  ]).then(([schedules, exams]) => {
    allEvents = loadEvents(schedules, exams);
    renderCalendar();
  });

  // 네비게이션
  document.getElementById("prevBtn").addEventListener("click", () => {
    curMonth--;
    if (curMonth < 0) { curMonth = 11; curYear--; }
    renderCalendar();
  });
  document.getElementById("nextBtn").addEventListener("click", () => {
    curMonth++;
    if (curMonth > 11) { curMonth = 0; curYear++; }
    renderCalendar();
  });
  document.getElementById("todayBtn").addEventListener("click", () => {
    curYear = today.getFullYear();
    curMonth = today.getMonth();
    renderCalendar();
  });

  // 시리즈 필터
  seriesFilter.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-series]");
    if (!btn) return;
    activeSeries = btn.dataset.series;
    seriesFilter.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    renderCalendar();
  });
})();

// index.html — D-Day 섹션 & 이번달 일정 동적 업데이트
function examPath(name) { return encodeURIComponent(name).replace(/%28/g,'(').replace(/%29/g,')'); }
(function () {
  const ddayGrid = document.getElementById("ddayGrid");
  const monthTable = document.getElementById("monthTableBody");
  const monthTitle = document.getElementById("monthTitle");

  if (!ddayGrid && !monthTable) return;

  const today = new Date();
  const thisYear = today.getFullYear();
  const thisMonth = today.getMonth() + 1;

  if (monthTitle) {
    monthTitle.textContent = `${thisYear}년 ${thisMonth}월`;
  }

  function dday(dateStr) {
    const d = new Date(dateStr);
    d.setHours(0, 0, 0, 0);
    const t = new Date();
    t.setHours(0, 0, 0, 0);
    return Math.round((d - t) / 86400000);
  }

  function ddayLabel(diff) {
    if (diff < 0) return { text: "종료", cls: "done" };
    if (diff === 0) return { text: "오늘", cls: "urgent" };
    if (diff <= 3) return { text: `D-${diff}`, cls: "urgent" };
    if (diff <= 7) return { text: `D-${diff}`, cls: "warning" };
    return { text: `D-${diff}`, cls: "normal" };
  }

  fetch("/data/upcoming.json")
    .then((r) => r.json())
    .then((data) => {
      const items = data.items || [];

      // D-Day 카드 (최대 6개, 30일 이내)
      if (ddayGrid) {
        const upcoming = items.filter((i) => i.dday >= -1 && i.dday <= 30).slice(0, 6);
        if (upcoming.length > 0) {
          ddayGrid.innerHTML = upcoming
            .map((item) => {
              const { text, cls } = ddayLabel(item.dday);
              const isOngoing = item.dday >= 0 && item.event.includes("접수");
              return `
              <a href="/exam/${examPath(item.name)}.html" class="dday-card ${isOngoing ? "ongoing" : ""}">
                <div class="dday-top">
                  <div class="dday-name">${item.name}</div>
                  <span class="dday-pill ${cls}">${isOngoing && item.dday > 0 ? "접수중" : text}</span>
                </div>
                <div class="dday-event">${item.round} ${item.event}</div>
                <div class="dday-date">${item.date}</div>
              </a>`;
            })
            .join("");
        }
      }

      // 이번달 일정 테이블
      if (monthTable) {
        const thisMonthItems = items.filter((i) => {
          const d = new Date(i.date);
          return d.getFullYear() === thisYear && d.getMonth() + 1 === thisMonth;
        });
        if (thisMonthItems.length > 0) {
          monthTable.innerHTML = thisMonthItems
            .map((item) => {
              const diff = dday(item.date);
              const chipCls = diff < 0 ? "done" : diff === 0 ? "ongoing" : "";
              return `
              <tr>
                <td><strong>${item.name}</strong></td>
                <td class="td-round">${item.round}</td>
                <td>${item.event}</td>
                <td><span class="date-chip ${chipCls}">${item.date.slice(5)}</span></td>
                <td><a href="/exam/${examPath(item.name)}.html" style="color:var(--primary);font-size:0.8125rem;font-weight:500;">→ 상세</a></td>
              </tr>`;
            })
            .join("");
        }
      }
    })
    .catch(() => {
      // 데이터 로드 실패 시 정적 콘텐츠 그대로 유지
    });
})();

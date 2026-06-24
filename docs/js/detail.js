/* detail.js — 자격증 상세 페이지 동작 (D-Day 카운트다운 + Chart.js) */

(function () {
  'use strict';

  /* ── D-Day 카운트다운 ── */
  function calcDday(dateStr) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const target = new Date(dateStr);
    target.setHours(0, 0, 0, 0);
    return Math.ceil((target - today) / 86400000);
  }

  function updateBanner() {
    const banner = document.getElementById('dday-banner');
    if (!banner) return;
    const endDateStr = banner.dataset.end;
    const startDateStr = banner.dataset.start;
    const label = banner.querySelector('.banner-label');
    const ddayEl = banner.querySelector('.banner-dday');
    if (!endDateStr || !ddayEl) return;

    const daysToEnd = calcDday(endDateStr);
    const daysToStart = startDateStr ? calcDday(startDateStr) : null;

    if (daysToStart !== null && daysToStart > 0) {
      // 접수 시작 전
      banner.className = 'dday-banner color-blue';
      if (label) label.textContent = banner.dataset.eventLabel || '원서접수 시작까지';
      ddayEl.textContent = 'D-' + daysToStart;
    } else if (daysToEnd >= 0) {
      // 접수 진행중
      banner.className = 'dday-banner color-green';
      if (label) label.textContent = '접수 진행중 — 마감까지';
      ddayEl.textContent = daysToEnd === 0 ? 'D-Day' : 'D-' + daysToEnd;
    } else {
      // 접수 종료 (다음 이벤트로)
      banner.className = 'dday-banner color-blue';
      const nextLabel = banner.dataset.nextLabel;
      const nextDate = banner.dataset.nextDate;
      if (nextDate) {
        const daysToNext = calcDday(nextDate);
        if (label) label.textContent = nextLabel || '다음 일정까지';
        ddayEl.textContent = daysToNext > 0 ? 'D-' + daysToNext : (daysToNext === 0 ? 'D-Day' : 'D+' + Math.abs(daysToNext));
      }
    }
  }

  /* ── Chart.js 차트 렌더링 ── */
  function renderCharts() {
    const statsEl = document.getElementById('stats-data');
    if (!statsEl) return;

    let stats;
    try { stats = JSON.parse(statsEl.textContent); } catch (e) { return; }

    const years = stats.map(s => s.year + '년');
    const writtenRates = stats.map(s => s.writtenPassRate);
    const practicalRates = stats.map(s => s.practicalPassRate);
    const writtenApplicants = stats.map(s => s.writtenApplicants);

    const baseOpts = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => ctx.parsed.y + '%'
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          max: 100,
          ticks: { callback: v => v + '%', font: { size: 11 } },
          grid: { color: '#F3F4F6' }
        },
        x: { ticks: { font: { size: 11 } }, grid: { display: false } }
      }
    };

    const hasWritten = writtenRates.some(v => v > 0);
    const hasPractical = practicalRates.some(v => v > 0);
    const hasApplicants = writtenApplicants.some(v => v > 0);

    const writtenCtx = document.getElementById('writtenChart');
    if (writtenCtx) {
      if (hasWritten) {
        new Chart(writtenCtx, {
          type: 'bar',
          data: {
            labels: years,
            datasets: [{
              data: writtenRates,
              backgroundColor: '#BFDBFE',
              borderColor: '#2563EB',
              borderWidth: 2,
              borderRadius: 6,
              borderSkipped: false
            }]
          },
          options: baseOpts
        });
      } else {
        writtenCtx.closest('.chart-box').style.display = 'none';
      }
    }

    const practicalCtx = document.getElementById('practicalChart');
    if (practicalCtx && !hasPractical) {
      practicalCtx.closest('.chart-box').style.display = 'none';
    }
    if (practicalCtx && hasPractical) {
      new Chart(practicalCtx, {
        type: 'bar',
        data: {
          labels: years,
          datasets: [{
            data: practicalRates,
            backgroundColor: '#BBF7D0',
            borderColor: '#16A34A',
            borderWidth: 2,
            borderRadius: 6,
            borderSkipped: false
          }]
        },
        options: {
          ...baseOpts,
          plugins: {
            ...baseOpts.plugins,
            tooltip: { callbacks: { label: ctx => ctx.parsed.y + '%' } }
          }
        }
      });
    }

    if (!hasWritten && !hasPractical) {
      const rateSection = document.querySelector('.chart-grid');
      if (rateSection) rateSection.closest('.content-section').style.display = 'none';
    }

    const applicantsCtx = document.getElementById('applicantsChart');
    if (applicantsCtx && !hasApplicants) {
      const section = applicantsCtx.closest('.content-section') || applicantsCtx.closest('.chart-box');
      if (section) section.style.display = 'none';
    }
    if (applicantsCtx && hasApplicants) {
      new Chart(applicantsCtx, {
        type: 'line',
        data: {
          labels: years,
          datasets: [{
            label: '필기 응시자수',
            data: writtenApplicants,
            borderColor: '#2563EB',
            backgroundColor: 'rgba(37,99,235,0.08)',
            tension: 0.35,
            fill: true,
            pointRadius: 5,
            pointBackgroundColor: '#2563EB'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: ctx => ctx.parsed.y.toLocaleString() + '명'
              }
            }
          },
          scales: {
            y: {
              beginAtZero: false,
              ticks: {
                callback: v => (v / 10000).toFixed(0) + '만',
                font: { size: 11 }
              },
              grid: { color: '#F3F4F6' }
            },
            x: { ticks: { font: { size: 11 } }, grid: { display: false } }
          }
        }
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    updateBanner();
    renderCharts();
  });
})();

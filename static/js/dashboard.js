/*
 * dashboard.js: fetches live, user-scoped chart data from Django and draws
 * it with Chart.js (a charting library only; no frontend framework).
 */
(function () {
  "use strict";

  const root = document.querySelector("[data-dashboard]");
  if (!root || typeof window.Chart === "undefined") return;

  const COLORS = {
    primary: "#123D2B",
    secondary: "#1C5A3E",
    accent: "#A3D9B1",
    text: "#25352D",
    muted: "#66756C",
    border: "#DCE6DE",
    negative: "#B03A2E",
    warning: "#D39B19",
  };
  // Green-led categorical palette for the category doughnut.
  const PALETTE = ["#123D2B", "#3E8E5E", "#A3D9B1", "#D39B19", "#6C9A8B", "#B03A2E", "#4F6D7A", "#C7B98A", "#8BBF9F", "#2F4F4F"];

  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.color = COLORS.muted;
  Chart.defaults.borderColor = COLORS.border;
  Chart.defaults.plugins.legend.labels.boxWidth = 12;
  Chart.defaults.maintainAspectRatio = false;

  const ksh = function (value) {
    return "KSh " + Number(value).toLocaleString("en-KE", { maximumFractionDigits: 0 });
  };

  const tooltipKsh = {
    callbacks: {
      label: function (ctx) {
        const label = ctx.dataset.label ? ctx.dataset.label + ": " : "";
        const value = ctx.parsed.y !== undefined ? ctx.parsed.y : ctx.parsed;
        return label + ksh(value);
      },
    },
  };

  function showEmpty(key, isEmpty) {
    const note = document.querySelector("[data-empty='" + key + "']");
    if (note) note.hidden = !isEmpty;
  }

  function drawTrend(data) {
    new Chart(document.getElementById("chart-trend"), {
      type: "bar",
      data: {
        labels: data.labels,
        datasets: [
          { label: "Income", data: data.income, backgroundColor: COLORS.accent, borderRadius: 4 },
          { label: "Expenses", data: data.expenses, backgroundColor: COLORS.primary, borderRadius: 4 },
        ],
      },
      options: {
        plugins: { tooltip: tooltipKsh },
        scales: { y: { beginAtZero: true, ticks: { callback: ksh } }, x: { grid: { display: false } } },
      },
    });
  }

  function drawCategories(data) {
    const empty = data.values.length === 0;
    showEmpty("categories", empty);
    if (empty) return;
    new Chart(document.getElementById("chart-categories"), {
      type: "doughnut",
      data: {
        labels: data.labels,
        datasets: [{ data: data.values, backgroundColor: PALETTE, borderColor: "#fff", borderWidth: 2 }],
      },
      options: {
        cutout: "62%",
        plugins: {
          legend: { position: "right" },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                const total = ctx.dataset.data.reduce(function (a, b) { return a + b; }, 0);
                const pct = total ? Math.round((ctx.parsed / total) * 100) : 0;
                return ctx.label + ": " + ksh(ctx.parsed) + " (" + pct + "%)";
              },
            },
          },
        },
      },
    });
  }

  function drawDaily(data) {
    const labels = data.labels.map(function (iso) {
      const d = new Date(iso + "T00:00:00");
      return d.toLocaleDateString("en-KE", { day: "numeric", month: "short" });
    });
    new Chart(document.getElementById("chart-daily"), {
      type: "line",
      data: {
        labels: labels,
        datasets: [{
          label: "Spent",
          data: data.values,
          borderColor: COLORS.secondary,
          backgroundColor: "rgba(163, 217, 177, 0.35)",
          fill: true,
          tension: 0.25,
          pointRadius: data.values.length > 40 ? 0 : 2,
        }],
      },
      options: {
        plugins: { legend: { display: false }, tooltip: tooltipKsh },
        scales: {
          y: { beginAtZero: true, ticks: { callback: ksh } },
          x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } },
        },
      },
    });
  }

  function drawBudgets(budgets) {
    const empty = budgets.length === 0;
    showEmpty("budgets", empty);
    if (empty) return;
    const colorFor = function (state) {
      if (state === "exceeded") return COLORS.negative;
      if (state === "warning") return COLORS.warning;
      return COLORS.secondary;
    };
    new Chart(document.getElementById("chart-budgets"), {
      type: "bar",
      data: {
        labels: budgets.map(function (b) { return b.name; }),
        datasets: [{
          label: "% used",
          data: budgets.map(function (b) { return b.percent; }),
          backgroundColor: budgets.map(function (b) { return colorFor(b.state); }),
          borderRadius: 4,
          maxBarThickness: 36,
        }],
      },
      options: {
        indexAxis: "y",
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: function (ctx) { return ctx.parsed.x + "% used"; } } },
        },
        scales: {
          x: { beginAtZero: true, suggestedMax: 100, ticks: { callback: function (v) { return v + "%"; } } },
          y: { grid: { display: false } },
        },
      },
    });
  }

  fetch(root.dataset.chartUrl, { credentials: "same-origin", headers: { Accept: "application/json" } })
    .then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    })
    .then(function (data) {
      drawTrend(data.trend);
      drawCategories(data.categories);
      drawDaily(data.daily);
      drawBudgets(data.budgets);
    })
    .catch(function () {
      root.insertAdjacentHTML(
        "beforebegin",
        '<div class="alert alert--warning">Charts could not be loaded. Check your connection and refresh.</div>'
      );
    });
})();

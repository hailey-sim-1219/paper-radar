const dashboardState = {
  papers: [],
  filtered: [],
  charts: {},
};

const dashboardColors = {
  ink: "#252b31",
  muted: "#737a80",
  line: "#e8e6e1",
  peach: "#e99a67",
  yellow: "#f4d978",
  sky: "#9bc9df",
};

const $ = selector => document.querySelector(selector);

function escapeHtml(value = "") {
  const element = document.createElement("div");
  element.textContent = String(value);
  return element.innerHTML;
}

function formatDate(value) {
  if (!value) return "날짜 미상";

  const parsedDate = new Date(`${value}T00:00:00`);

  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return parsedDate.toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatUpdatedAt(value) {
  if (!value) {
    return "마지막 업데이트 정보 없음";
  }

  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return "마지막 업데이트 정보 없음";
  }

  return `마지막 업데이트 ${parsedDate.toLocaleString("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  })}`;
}

function paperUrl(paper) {
  return (
    paper.doi_url ||
    paper.journal_url ||
    paper.url ||
    "#"
  );
}

function uniqueValues(papers, key) {
  return [
    ...new Set(
      papers
        .flatMap(paper => paper[key] || [])
        .filter(Boolean)
    ),
  ].sort((a, b) => a.localeCompare(b));
}

function countValues(papers, key) {
  const counts = new Map();

  papers.forEach(paper => {
    const values = [...new Set(paper[key] || [])];

    values.forEach(value => {
      counts.set(value, (counts.get(value) || 0) + 1);
    });
  });

  return [...counts.entries()]
    .map(([name, value]) => ({
      name,
      value,
    }))
    .sort((a, b) => {
      return b.value - a.value || a.name.localeCompare(b.name);
    });
}

function addOptions(select, values) {
  values.forEach(value => {
    const option = document.createElement("option");

    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
}

function loadSavedCount() {
  try {
    const saved = JSON.parse(
      localStorage.getItem("paperRadarSavedPapers") || "[]"
    );

    $("#saved-count").textContent =
      Array.isArray(saved) ? saved.length : 0;
  } catch {
    $("#saved-count").textContent = "0";
  }
}

function getCutoffDate(months) {
  if (months === "all") {
    return null;
  }

  const cutoffDate = new Date();

  cutoffDate.setHours(0, 0, 0, 0);
  cutoffDate.setMonth(
    cutoffDate.getMonth() - Number(months)
  );

  return cutoffDate;
}

function applyDashboardFilters() {
  const period = $("#period-filter").value;
  const journal = $("#dashboard-journal-filter").value;
  const topic = $("#dashboard-topic-filter").value;
  const method = $("#dashboard-method-filter").value;
  const cutoffDate = getCutoffDate(period);

  dashboardState.filtered =
    dashboardState.papers.filter(paper => {
      const publicationDate = paper.publication_date
        ? new Date(`${paper.publication_date}T00:00:00`)
        : null;

      const matchesPeriod =
        !cutoffDate ||
        (
          publicationDate &&
          !Number.isNaN(publicationDate.getTime()) &&
          publicationDate >= cutoffDate
        );

      const matchesJournal =
        !journal || paper.journal === journal;

      const matchesTopic =
        !topic ||
        (paper.topics || []).includes(topic);

      const matchesMethod =
        !method ||
        (paper.methods || []).includes(method);

      return (
        matchesPeriod &&
        matchesJournal &&
        matchesTopic &&
        matchesMethod
      );
    });

  dashboardState.filtered.sort((a, b) => {
    return (b.publication_date || "").localeCompare(
      a.publication_date || ""
    );
  });

  renderDashboard();
}

function renderSelectionSummary() {
  const labels = [];

  const periodSelect = $("#period-filter");
  const journal =
    $("#dashboard-journal-filter").value;
  const topic =
    $("#dashboard-topic-filter").value;
  const method =
    $("#dashboard-method-filter").value;

  if (periodSelect.value !== "all") {
    labels.push(
      periodSelect.options[
        periodSelect.selectedIndex
      ].textContent
    );
  }

  if (journal) {
    labels.push(journal);
  }

  if (topic) {
    labels.push(topic);
  }

  if (method) {
    labels.push(method);
  }

  if (labels.length) {
    $("#selection-summary").textContent =
      `${labels.join(" · ")} · ` +
      `${dashboardState.filtered.length}편`;
  } else {
    $("#selection-summary").textContent =
      `전체 논문 ${dashboardState.filtered.length}편`;
  }
}

function renderKpis() {
  const papers = dashboardState.filtered;
  const topics = uniqueValues(papers, "topics");
  const methods = uniqueValues(papers, "methods");

  const thirtyDaysAgo = new Date();

  thirtyDaysAgo.setHours(0, 0, 0, 0);
  thirtyDaysAgo.setDate(
    thirtyDaysAgo.getDate() - 30
  );

  const newPaperCount = papers.filter(paper => {
    if (!paper.first_seen_at) {
      return false;
    }

    const firstSeenDate = new Date(
      `${paper.first_seen_at}T00:00:00`
    );

    return (
      !Number.isNaN(firstSeenDate.getTime()) &&
      firstSeenDate >= thirtyDaysAgo
    );
  }).length;

  $("#kpi-papers").textContent =
    papers.length.toLocaleString("ko-KR");

  $("#kpi-topics").textContent =
    topics.length.toLocaleString("ko-KR");

  $("#kpi-methods").textContent =
    methods.length.toLocaleString("ko-KR");

  $("#kpi-new").textContent =
    newPaperCount.toLocaleString("ko-KR");
}

function ensureChart(name, selector) {
  if (!window.echarts) {
    throw new Error(
      "차트 라이브러리를 불러오지 못했습니다."
    );
  }

  if (!dashboardState.charts[name]) {
    const container = $(selector);

    if (!container) {
      throw new Error(
        `${selector} 차트 영역을 찾지 못했습니다.`
      );
    }

    dashboardState.charts[name] =
      echarts.init(container);
  }

  return dashboardState.charts[name];
}

function renderBarChart(
  name,
  selector,
  data,
  color,
  filterSelector
) {
  const chart = ensureChart(name, selector);
  const visibleData = data.slice(0, 15);

  chart.setOption(
    {
      animationDuration: 450,
      color: [color],

      grid: {
        top: 12,
        right: 35,
        bottom: 28,
        left: 165,
      },

      tooltip: {
        trigger: "axis",
        axisPointer: {
          type: "shadow",
        },
        formatter(params) {
          const item = params[0];

          return (
            `${escapeHtml(item.name)}<br>` +
            `<strong>${item.value}편</strong>`
          );
        },
      },

      xAxis: {
        type: "value",
        minInterval: 1,

        axisLine: {
          show: false,
        },

        axisTick: {
          show: false,
        },

        splitLine: {
          lineStyle: {
            color: dashboardColors.line,
          },
        },

        axisLabel: {
          color: dashboardColors.muted,
          fontSize: 10,
        },
      },

      yAxis: {
        type: "category",
        inverse: true,
        data: visibleData.map(item => item.name),

        axisLine: {
          show: false,
        },

        axisTick: {
          show: false,
        },

        axisLabel: {
          color: dashboardColors.ink,
          fontSize: 10,
          width: 145,
          overflow: "truncate",
        },
      },

      series: [
        {
          type: "bar",
          data: visibleData.map(item => item.value),
          barMaxWidth: 18,

          itemStyle: {
            borderRadius: [0, 5, 5, 0],
          },

          label: {
            show: true,
            position: "right",
            color: dashboardColors.muted,
            fontSize: 10,
            formatter: "{c}",
          },
        },
      ],
    },
    true
  );

  chart.off("click");

  chart.on("click", params => {
    const select = $(filterSelector);

    if (select.value === params.name) {
      select.value = "";
    } else {
      select.value = params.name;
    }

    applyDashboardFilters();
  });
}

function renderHeatmap() {
  const chart = ensureChart(
    "heatmap",
    "#heatmap-chart"
  );

  const papers = dashboardState.filtered;

  const topics = countValues(
    papers,
    "topics"
  ).map(item => item.name);

  const methods = countValues(
    papers,
    "methods"
  ).map(item => item.name);

  const heatmapData = [];

  topics.forEach((topic, topicIndex) => {
    methods.forEach((method, methodIndex) => {
      const count = papers.filter(paper => {
        return (
          (paper.topics || []).includes(topic) &&
          (paper.methods || []).includes(method)
        );
      }).length;

      heatmapData.push([
        methodIndex,
        topicIndex,
        count,
      ]);
    });
  });

  const maximum = Math.max(
    1,
    ...heatmapData.map(item => item[2])
  );

  chart.setOption(
    {
      animationDuration: 450,

      tooltip: {
        position: "top",

        formatter(params) {
          const [
            methodIndex,
            topicIndex,
            value,
          ] = params.value;

          return (
            `${escapeHtml(topics[topicIndex])}<br>` +
            `${escapeHtml(methods[methodIndex])}<br>` +
            `<strong>${value}편</strong>`
          );
        },
      },

      grid: {
        top: 15,
        right: 25,
        bottom: 145,
        left: 175,
      },

      xAxis: {
        type: "category",
        data: methods,

        splitArea: {
          show: true,
        },

        axisLine: {
          lineStyle: {
            color: dashboardColors.line,
          },
        },

        axisTick: {
          show: false,
        },

        axisLabel: {
          interval: 0,
          rotate: 45,
          color: dashboardColors.muted,
          fontSize: 9,
        },
      },

      yAxis: {
        type: "category",
        data: topics,

        splitArea: {
          show: true,
        },

        axisLine: {
          lineStyle: {
            color: dashboardColors.line,
          },
        },

        axisTick: {
          show: false,
        },

        axisLabel: {
          color: dashboardColors.ink,
          fontSize: 9,
          width: 155,
          overflow: "truncate",
        },
      },

      visualMap: {
        min: 0,
        max: maximum,
        calculable: true,
        orient: "horizontal",
        left: "center",
        bottom: 5,

        inRange: {
          color: [
            "#fff7ed",
            "#f6c79f",
            dashboardColors.peach,
          ],
        },

        textStyle: {
          color: dashboardColors.muted,
          fontSize: 9,
        },
      },

      series: [
        {
          name: "논문 수",
          type: "heatmap",
          data: heatmapData,

          label: {
            show: true,
            color: dashboardColors.ink,
            fontSize: 9,

            formatter(params) {
              return params.value[2] || "";
            },
          },

          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: "rgba(0,0,0,0.18)",
            },
          },
        },
      ],
    },
    true
  );

  chart.off("click");

  chart.on("click", params => {
    const [
      methodIndex,
      topicIndex,
    ] = params.value;

    $("#dashboard-topic-filter").value =
      topics[topicIndex];

    $("#dashboard-method-filter").value =
      methods[methodIndex];

    applyDashboardFilters();
  });
}

function monthKey(value) {
  return value ? value.slice(0, 7) : "";
}

function createMonthRange(start, end) {
  if (!start || !end) {
    return [];
  }

  const result = [];

  const cursor = new Date(
    `${start}-01T00:00:00`
  );

  const last = new Date(
    `${end}-01T00:00:00`
  );

  while (cursor <= last) {
    const year = cursor.getFullYear();

    const month = String(
      cursor.getMonth() + 1
    ).padStart(2, "0");

    result.push(`${year}-${month}`);

    cursor.setMonth(
      cursor.getMonth() + 1
    );
  }

  return result;
}

function renderTrendChart() {
  const chart = ensureChart(
    "trend",
    "#trend-chart"
  );

  const datedPapers =
    dashboardState.filtered.filter(
      paper => paper.publication_date
    );

  const counts = new Map();

  datedPapers.forEach(paper => {
    const key = monthKey(
      paper.publication_date
    );

    counts.set(
      key,
      (counts.get(key) || 0) + 1
    );
  });

  const existingMonths = [
    ...counts.keys(),
  ].sort();

  const months = existingMonths.length
    ? createMonthRange(
        existingMonths[0],
        existingMonths[
          existingMonths.length - 1
        ]
      )
    : [];

  chart.setOption(
    {
      animationDuration: 450,
      color: [dashboardColors.peach],

      grid: {
        top: 30,
        right: 28,
        bottom: 45,
        left: 48,
      },

      tooltip: {
        trigger: "axis",

        formatter(params) {
          return (
            `${params[0].axisValue}<br>` +
            `<strong>${params[0].value}편</strong>`
          );
        },
      },

      xAxis: {
        type: "category",
        boundaryGap: false,
        data: months,

        axisLine: {
          lineStyle: {
            color: dashboardColors.line,
          },
        },

        axisTick: {
          show: false,
        },

        axisLabel: {
          color: dashboardColors.muted,
          fontSize: 10,
        },
      },

      yAxis: {
        type: "value",
        minInterval: 1,

        axisLine: {
          show: false,
        },

        axisTick: {
          show: false,
        },

        axisLabel: {
          color: dashboardColors.muted,
          fontSize: 10,
        },

        splitLine: {
          lineStyle: {
            color: dashboardColors.line,
          },
        },
      },

      series: [
        {
          type: "line",
          smooth: 0.3,
          symbolSize: 7,

          data: months.map(month => {
            return counts.get(month) || 0;
          }),

          lineStyle: {
            width: 3,
          },

          areaStyle: {
            color: "rgba(233,154,103,0.16)",
          },
        },
      ],
    },
    true
  );
}

function getCombinationCounts(papers) {
  const counts = new Map();

  papers.forEach(paper => {
    const topics = [
      ...new Set(paper.topics || []),
    ];

    const methods = [
      ...new Set(paper.methods || []),
    ];

    topics.forEach(topic => {
      methods.forEach(method => {
        const key = JSON.stringify([
          topic,
          method,
        ]);

        counts.set(
          key,
          (counts.get(key) || 0) + 1
        );
      });
    });
  });

  return [...counts.entries()]
    .map(([key, count]) => {
      const [topic, method] =
        JSON.parse(key);

      return {
        topic,
        method,
        count,
      };
    })
    .sort((a, b) => {
      return (
        b.count - a.count ||
        a.topic.localeCompare(b.topic)
      );
    });
}

function renderCombinationTable() {
  const papers = dashboardState.filtered;

  const combinations =
    getCombinationCounts(papers).slice(0, 15);

  const tbody = $("#combination-table");

  if (!combinations.length) {
    tbody.innerHTML = `
      <tr>
        <td
          colspan="5"
          class="dashboard-empty"
        >
          조건에 맞는 조합이 없습니다.
        </td>
      </tr>
    `;

    return;
  }

  tbody.innerHTML = combinations
    .map((item, index) => {
      const share = papers.length
        ? (item.count / papers.length) * 100
        : 0;

      return `
        <tr
          data-topic="${escapeHtml(item.topic)}"
          data-method="${escapeHtml(item.method)}"
        >
          <td>${index + 1}</td>
          <td>${escapeHtml(item.topic)}</td>
          <td>${escapeHtml(item.method)}</td>
          <td>${item.count}편</td>
          <td>${share.toFixed(1)}%</td>
        </tr>
      `;
    })
    .join("");
}

function renderPaperList() {
  const papers =
    dashboardState.filtered.slice(0, 25);

  const container =
    $("#selected-paper-list");

  if (dashboardState.filtered.length > 25) {
    $("#paper-list-description").textContent =
      `총 ${dashboardState.filtered.length}편 중 ` +
      "최신 25편을 표시합니다.";
  } else {
    $("#paper-list-description").textContent =
      `총 ${dashboardState.filtered.length}편을 ` +
      "표시합니다.";
  }

  if (!papers.length) {
    container.innerHTML = `
      <div class="dashboard-empty">
        조건에 맞는 논문이 없습니다.
      </div>
    `;

    return;
  }

  container.innerHTML = papers
    .map(paper => {
      const topicTags = (
        paper.topics || []
      )
        .map(topic => {
          return `
            <span>
              #${escapeHtml(
                topic.replaceAll(" ", "-")
              )}
            </span>
          `;
        })
        .join("");

      const methodTags = (
        paper.methods || []
      )
        .map(method => {
          return `
            <span class="method">
              #${escapeHtml(
                method.replaceAll(" ", "-")
              )}
            </span>
          `;
        })
        .join("");

      return `
        <article class="dashboard-paper">
          <div class="dashboard-paper-meta">
            <strong>
              ${escapeHtml(
                paper.journal_short ||
                paper.journal ||
                "저널 미상"
              )}
            </strong>

            <span>
              ${formatDate(
                paper.publication_date
              )}
            </span>
          </div>

          <div>
            <h3>
              <a
                href="${escapeHtml(
                  paperUrl(paper)
                )}"
                target="_blank"
                rel="noreferrer"
              >
                ${escapeHtml(
                  paper.title || "Untitled"
                )}
              </a>
            </h3>

            <p>
              ${escapeHtml(
                (paper.authors || []).join(", ")
              )}
            </p>

            <div class="dashboard-paper-tags">
              ${topicTags}
              ${methodTags}
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderDashboard() {
  renderSelectionSummary();
  renderKpis();

  try {
    renderBarChart(
      "topics",
      "#topic-chart",
      countValues(
        dashboardState.filtered,
        "topics"
      ),
      dashboardColors.yellow,
      "#dashboard-topic-filter"
    );

    renderBarChart(
      "methods",
      "#method-chart",
      countValues(
        dashboardState.filtered,
        "methods"
      ),
      dashboardColors.sky,
      "#dashboard-method-filter"
    );

    renderHeatmap();
    renderTrendChart();

    $("#dashboard-error").hidden = true;
  } catch (error) {
    $("#dashboard-error").textContent =
      error.message;

    $("#dashboard-error").hidden = false;

    console.error(error);
  }

  renderCombinationTable();
  renderPaperList();
}

function resetDashboardFilters() {
  $("#period-filter").value = "all";

  $("#dashboard-journal-filter").value = "";

  $("#dashboard-topic-filter").value = "";

  $("#dashboard-method-filter").value = "";

  applyDashboardFilters();
}

function bindEvents() {
  const filters = [
    "#period-filter",
    "#dashboard-journal-filter",
    "#dashboard-topic-filter",
    "#dashboard-method-filter",
  ];

  filters.forEach(selector => {
    $(selector).addEventListener(
      "change",
      applyDashboardFilters
    );
  });

  $("#dashboard-reset").addEventListener(
    "click",
    resetDashboardFilters
  );

  $("#combination-table").addEventListener(
    "click",
    event => {
      const row = event.target.closest(
        "tr[data-topic][data-method]"
      );

      if (!row) {
        return;
      }

      $("#dashboard-topic-filter").value =
        row.dataset.topic;

      $("#dashboard-method-filter").value =
        row.dataset.method;

      applyDashboardFilters();

      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    }
  );

  window.addEventListener("resize", () => {
    Object.values(
      dashboardState.charts
    ).forEach(chart => {
      chart.resize();
    });
  });
}

async function initDashboard() {
  loadSavedCount();
  bindEvents();

  try {
    const response = await fetch(
      `data/papers.json?v=${Date.now()}`
    );

    if (!response.ok) {
      throw new Error(
        `논문 데이터를 불러오지 못했습니다. ` +
        `HTTP ${response.status}`
      );
    }

    const payload =
      await response.json();

    dashboardState.papers =
      Array.isArray(payload.papers)
        ? payload.papers
        : [];

    const journals = [
      ...new Set(
        dashboardState.papers
          .map(paper => paper.journal)
          .filter(Boolean)
      ),
    ].sort((a, b) => a.localeCompare(b));

    const topics = uniqueValues(
      dashboardState.papers,
      "topics"
    );

    const methods = uniqueValues(
      dashboardState.papers,
      "methods"
    );

    addOptions(
      $("#dashboard-journal-filter"),
      journals
    );

    addOptions(
      $("#dashboard-topic-filter"),
      topics
    );

    addOptions(
      $("#dashboard-method-filter"),
      methods
    );

    $("#updated").textContent =
      formatUpdatedAt(payload.updated_at);

    applyDashboardFilters();
  } catch (error) {
    $("#updated").textContent =
      "데이터를 불러오지 못했습니다";

    $("#dashboard-error").textContent =
      error.message;

    $("#dashboard-error").hidden = false;

    console.error(error);
  }
}

initDashboard();

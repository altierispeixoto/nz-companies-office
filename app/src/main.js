import { Cosmograph } from "@cosmograph/cosmograph";
import { CosmographTypeColorLegend } from "@cosmograph/cosmograph";
import { CosmographSearch } from "@cosmograph/cosmograph";
import * as duckdb from "@duckdb/duckdb-wasm";
import "./style.css";

const SHAREHOLDER_COLOR = "#2dd4bf";
const COMPANY_COLOR = "#f59e0b";

const container = document.getElementById("graph-container");
const statusMsg = document.getElementById("status-msg");
const statsEl = document.getElementById("stats");
const legendContainer = document.getElementById("legend-container");
const searchContainer = document.getElementById("search-container");
const refreshBtn = document.getElementById("refresh-btn");
const statusFilter = document.getElementById("status-filter");
const industryFilter = document.getElementById("industry-filter");
const limitSlider = document.getElementById("limit-slider");
const limitValue = document.getElementById("limit-value");
const minConnections = document.getElementById("min-connections");
const detailPanel = document.getElementById("detail-panel");
const panelTitle = document.getElementById("panel-title");
const panelContent = document.getElementById("panel-content");
const panelClose = document.getElementById("panel-close");

let cosmograph = null;
let legend = null;
let search = null;
let db = null;
let allNodes = [];
let nodeById = new Map();
let navHistory = [];
const panelBack = document.getElementById("panel-back");

function showStatus(msg, isError = false) {
  statusMsg.textContent = msg;
  statusMsg.style.color = isError ? "#ef5350" : "#9e9e9e";
}

const totalsEl = document.getElementById("totals");

let totalCompanies = 0;
const industryCodeMap = new Map();

async function fetchTotals() {
  if (!db) return;
  let conn;
  try {
    conn = await db.connect();
    const [compRow] = tableToObjects(await conn.query("SELECT COUNT(*) AS cnt FROM 'companies.parquet'"));
    const [shRow] = tableToObjects(await conn.query("SELECT COUNT(*) AS cnt FROM 'shareholders.parquet'"));
    const [holdRow] = tableToObjects(await conn.query("SELECT COUNT(*) AS cnt FROM 'holdings.parquet'"));
    totalCompanies = Number(compRow.cnt);
    limitSlider.max = totalCompanies;
    const curVal = parseInt(limitSlider.value, 10);
    limitSlider.value = Math.min(curVal, totalCompanies);
    limitValue.textContent = parseInt(limitSlider.value, 10) >= totalCompanies ? "All" : parseInt(limitSlider.value, 10).toLocaleString();
    totalsEl.innerHTML = `
      <div class="totals-row">
        <span class="totals-label">Database</span>
        <span class="totals-counts">${compRow.cnt.toLocaleString()} companies · ${shRow.cnt.toLocaleString()} shareholders · ${holdRow.cnt.toLocaleString()} holdings</span>
      </div>
    `;
  } catch (err) { console.error("fetchTotals error:", err); } finally {
    if (conn) await conn.close();
  }
}

function updateStats(meta) {
  if (!meta) return;
  statsEl.innerHTML = `
    <div class="stat"><span>Nodes</span><strong>${meta.node_count.toLocaleString()}</strong></div>
    <div class="stat"><span>Edges</span><strong>${meta.link_count.toLocaleString()}</strong></div>
    <div class="stat"><span>Companies</span><strong>${meta.company_count.toLocaleString()}</strong></div>
    <div class="stat"><span>Shareholders</span><strong>${meta.shareholder_count.toLocaleString()}</strong></div>
  `;
}

function closePanel() {
  detailPanel.classList.remove("visible");
  if (cosmograph) cosmograph.unselectAllPoints();
  navHistory = [];
  updateBackBtn();
}

panelClose.addEventListener("click", closePanel);

// Click items in the detail panel to navigate to that point
panelContent.addEventListener("click", (e) => {
  const item = e.target.closest("[data-point-id]");
  if (!item) return;
  const pointId = item.dataset.pointId;
  if (!pointId) return;
  cosmograph.getPointIndicesByIds([pointId]).then((indices) => {
    if (indices && indices[0] !== undefined && !Number.isNaN(indices[0])) {
      navigateTo(indices[0]);
    }
  });
});

// Navigation history — back/forward in the detail panel
function navigateTo(index) {
  const last = navHistory.length > 0 ? navHistory[navHistory.length - 1] : -1;
  if (last !== index) {
    navHistory.push(index);
  }
  updateBackBtn();
  showNodeDetails(index);
}

function goBack() {
  navHistory.pop();
  const prev = navHistory.length > 0 ? navHistory[navHistory.length - 1] : -1;
  if (prev === -1) {
    updateBackBtn();
    return;
  }
  showNodeDetails(prev);
  updateBackBtn();
}

function updateBackBtn() {
  panelBack.style.display = navHistory.length > 1 ? "" : "none";
}

panelBack.addEventListener("click", goBack);

async function showNodeDetails(index, pointPosition, event) {
  // Resolve point data via Cosmograph's own index → id mapping
  let point;
  try {
    const tbl = await cosmograph.getPointsByIndices([index]);
    if (tbl && tbl.numRows > 0) {
      const id = tbl.getChild("id")?.get(0);
      if (id) point = nodeById.get(id);
    }
  } catch (_) { /* fall through */ }
  if (!point) {
    point = allNodes[index];
    if (!point) return;
  }
  panelTitle.textContent = point.name;
  panelContent.innerHTML = '<div class="panel-loading">Loading...</div>';
  detailPanel.classList.add("visible");
  let conn;
  try {
    conn = await db.connect();
    if (point.type === "company") {
      // Highlight the clicked company + its shareholders
      const highlightIndices = [index];
      const connected = cosmograph.getConnectedPointIndices(index);
      if (connected) {
        for (const ci of connected) {
          if (ci !== undefined && !Number.isNaN(ci)) highlightIndices.push(ci);
        }
      }
      cosmograph.selectPoints(highlightIndices);
      const companyNumber = point.id.slice(1);
      const table = await conn.query(`
        SELECT shareholder_name,
               100.0 * shares / NULLIF(SUM(shares) OVER (PARTITION BY company_number), 0) AS percentage
        FROM 'holdings.parquet'
        WHERE company_number = '${companyNumber}'
        ORDER BY percentage DESC
      `);
      const shareholders = tableToObjects(table);
      let html = "";
      if (shareholders.length === 0) {
        html = '<div class="detail-empty">No shareholders found.</div>';
      } else {
        html = shareholders.map((r) => {
          const pct = typeof r.percentage === "number" ? r.percentage.toFixed(2) : r.percentage;
          return `
            <div class="detail-item" data-point-id="s${r.shareholder_name}">
              <span class="detail-item-name">${r.shareholder_name}</span>
              <span class="detail-type-badge shareholder">shareholder</span>
              <span class="detail-item-percent">${pct}%</span>
            </div>
          `;
        }).join("");
      }
      panelContent.innerHTML = html;
    } else {
      const shareholderName = point.id.slice(1).replace(/'/g, "''");

      // 1. Portfolio companies this shareholder invests in
      const holdTable = await conn.query(`
        SELECT c.name, c.status, c.company_number,
               100.0 * h.shares / NULLIF(h.total, 0) AS percentage
        FROM (
          SELECT *, SUM(shares) OVER (PARTITION BY company_number) AS total
          FROM 'holdings.parquet'
        ) h
        JOIN 'companies.parquet' c ON h.company_number = c.company_number
        WHERE h.shareholder_name = '${shareholderName}'
        ORDER BY percentage DESC
      `);
      const holdings = tableToObjects(holdTable);

      // 2. Co-investors — other shareholders who invest in the same companies
      const coTable = await conn.query(`
        WITH target_companies AS (
          SELECT company_number
          FROM 'holdings.parquet'
          WHERE shareholder_name = '${shareholderName}'
        ),
        target_count AS (
          SELECT COUNT(*) AS cnt FROM target_companies
        )
        SELECT h.shareholder_name AS peer_name,
               COUNT(DISTINCT h.company_number) AS company_count,
               100.0 * COUNT(DISTINCT h.company_number) / tt.cnt AS overlap_pct
        FROM 'holdings.parquet' h
        JOIN target_companies tc ON h.company_number = tc.company_number
        CROSS JOIN target_count tt
        WHERE h.shareholder_name != '${shareholderName}'
        GROUP BY h.shareholder_name, tt.cnt
        ORDER BY company_count DESC, overlap_pct DESC
        LIMIT 100
      `);
      const coInvestors = tableToObjects(coTable);

      // 3. Highlight clicked shareholder + portfolio companies + co-investors
      const highlightIndices = [index];

      // Portfolio companies: use Cosmograph's 1-hop connection from the clicked shareholder
      const connected = cosmograph.getConnectedPointIndices(index);
      if (connected) {
        for (const ci of connected) {
          if (ci !== undefined && !Number.isNaN(ci)) highlightIndices.push(ci);
        }
      }

      // Co-investors: resolve from SQL peer_name IDs
      const coIds = coInvestors.map((r) => "s" + r.peer_name);
      if (coIds.length > 0) {
        const peerIndices = await cosmograph.getPointIndicesByIds(coIds);
        if (peerIndices) {
          for (const pi of peerIndices) {
            if (pi !== undefined && !Number.isNaN(pi)) highlightIndices.push(pi);
          }
        }
      }

      cosmograph.selectPoints(highlightIndices);

      // 4. Render both sections
      let html = "";

      html += '<div class="panel-section">';
      html += '<h4 class="panel-section-title">Portfolio Companies</h4>';
      if (holdings.length === 0) {
        html += '<div class="detail-empty">No holdings found.</div>';
      } else {
        html += holdings.map((r) => {
          const pct = typeof r.percentage === "number" ? r.percentage.toFixed(2) : r.percentage;
          return `
            <div class="detail-item" data-point-id="c${r.company_number}">
              <span class="detail-item-name">${r.name}</span>
              <span class="detail-type-badge company">company</span>
              <span class="detail-item-percent">${pct}%</span>
            </div>
          `;
        }).join("");
      }
      html += "</div>";

      html += '<div class="panel-section">';
      html += '<h4 class="panel-section-title">Co-Investors</h4>';
      if (coInvestors.length === 0) {
        html += '<div class="detail-empty">No co-investors found.</div>';
      } else {
        html += coInvestors.map((r) => {
          const pct = typeof r.overlap_pct === "number" ? r.overlap_pct.toFixed(1) : r.overlap_pct;
          return `
            <div class="detail-item" data-point-id="s${r.peer_name}">
              <span class="detail-item-name">${r.peer_name}</span>
              <span class="detail-item-tag">${r.company_count}</span>
              <span class="detail-item-percent">${pct}%</span>
            </div>
          `;
        }).join("");
      }
      html += "</div>";

      panelContent.innerHTML = html;
    }
  } catch (err) {
    panelContent.innerHTML = `<div class="detail-empty">Error: ${err.message}</div>`;
    console.error(err);
  } finally {
    if (conn) { await conn.close(); }
  }
}

function tableToObjects(table) {
  const rows = [];
  for (let i = 0; i < table.numRows; i++) {
    const obj = {};
    for (const field of table.schema.fields) {
      const col = table.getChild(field.name);
      if (col) {
        obj[field.name] = col.get(i);
      }
    }
    rows.push(obj);
  }
  return rows;
}

async function initDuckDB() {
  showStatus("Initializing DuckDB-WASM...");

  const bundles = duckdb.getJsDelivrBundles();
  const bundle = await duckdb.selectBundle(bundles);
  const logger = new duckdb.ConsoleLogger();
  const worker = await duckdb.createWorker(bundle.mainWorker);
  const duckDb = new duckdb.AsyncDuckDB(logger, worker);
  await duckDb.instantiate(bundle.mainModule, bundle.pthreadWorker);
  await duckDb.open({ path: ":memory:" });

  showStatus("Loading parquet data...");

  for (const file of ["companies.parquet", "shareholders.parquet", "holdings.parquet", "industry.parquet", "industry_codes.parquet"]) {
    const resp = await fetch(`/${file}`);
    if (!resp.ok) {
      showStatus(`Failed to load ${file}`, true);
      return null;
    }
    const buf = new Uint8Array(await resp.arrayBuffer());
    await duckDb.registerFileBuffer(file, buf);
  }

  return duckDb;
}

const MAX_VISIBLE_COMPANIES = 50000;

function buildCosmographConfig() {
  return {
    points: "_points",
    pointIdBy: "id",
    pointIndexBy: "idx",
    pointColorBy: "type",
    pointColorStrategy: "categorical",
    pointColorPalette: [SHAREHOLDER_COLOR, COMPANY_COLOR],
    pointSizeBy: "degree",
    pointSizeStrategy: "degree",
    pointSizeRange: [3, 18],
    pointLabelBy: "name",
    pointDefaultSize: 5,
    links: "_links",
    linkSourceBy: "source",
    linkSourceIndexBy: "sourceidx",
    linkTargetBy: "target",
    linkTargetIndexBy: "targetidx",
    linkDefaultColor: "rgba(255,255,255,0.08)",
    linkDefaultWidth: 0.6,
    curvedLinks: true,
    curvedLinkSegments: 4,
    curvedLinkWeight: 0.4,
    linkArrows: false,
    backgroundColor: "#0a0a14",
    simulationGravity: 0.2,
    simulationRepulsion: 2,
    simulationLinkSpring: 0.3,
    simulationLinkDistance: 40,
    simulationDecay: 80,
    showLabels: true,
    showDynamicLabels: true,
    showDynamicLabelsLimit: 60,
    showTopLabels: true,
    showTopLabelsLimit: 15,
    fitViewOnInit: true,
    fitViewPadding: 0.08,
    selectPointOnClick: true,
    focusPointOnClick: true,
    hoveredPointRingColor: "#2dd4bf",
    focusedPointRingColor: "#f59e0b",
    hoveredLinkColor: "rgba(255,255,255,0.3)",
    hoveredLinkWidthIncrease: 2,
    linkGreyoutOpacity: 0.03,
    pointGreyoutOpacity: 0.15,
    pointOpacity: 0.9,
  };
}

async function loadGraph() {
  if (!db) {
    showStatus("DuckDB not initialized", true);
    return;
  }

  const statusVal = statusFilter.value;
  const minCon = parseInt(minConnections.value, 10);
  const limit = Math.min(parseInt(limitSlider.value, 10), MAX_VISIBLE_COMPANIES);
  const limitClause = limit >= totalCompanies ? "" : `LIMIT ${limit}`;

  if (limit > 10000) {
    showStatus(`Loading ${limit.toLocaleString()} companies — browser may be slow…`);
  } else {
    showStatus("Building graph...");
  }

  const industryDesc = industryFilter.value.trim();
  const industryCode = industryDesc ? industryCodeMap.get(industryDesc) : "";
  const statusClause = statusVal ? `AND c.status = '${statusVal}'` : "";
  const industryClause = industryCode
    ? `AND c.company_number IN (SELECT company_number FROM 'industry.parquet' WHERE industry_code = '${industryCode}')`
    : "";

  let conn;
  try {
    conn = await db.connect();

    // ── Phase 1: filtered company list ──
    await conn.query(`
      CREATE OR REPLACE TABLE _top AS
      SELECT c.company_number, c.name, c.status
      FROM 'companies.parquet' c
      JOIN 'holdings.parquet' h ON c.company_number = h.company_number
      WHERE 1=1 ${statusClause} ${industryClause}
      GROUP BY c.company_number, c.name, c.status
      HAVING COUNT(DISTINCT h.shareholder_name) >= ${minCon}
      ORDER BY COUNT(DISTINCT h.shareholder_name) DESC
      ${limitClause}
    `);

    const [countRow] = tableToObjects(await conn.query("SELECT COUNT(*) AS cnt FROM _top"));
    if (Number(countRow.cnt) === 0) {
      showStatus("No data returned — try relaxing filters.", false);
      return;
    }

    // ── Phase 2: numeric indices for companies ──
    await conn.query(`
      CREATE OR REPLACE TABLE _comp_map AS
      SELECT company_number, name, status, row_number() OVER () AS idx
      FROM _top
    `);

    // ── Phase 3: numeric indices for shareholders (offset past companies) ──
    const [cc] = tableToObjects(await conn.query("SELECT COUNT(*) AS cnt FROM _comp_map"));
    await conn.query(`
      CREATE OR REPLACE TABLE _sh_map AS
      SELECT shareholder_name,
             ${cc.cnt} + row_number() OVER (ORDER BY shareholder_name) AS idx
      FROM (
        SELECT DISTINCT h.shareholder_name
        FROM 'holdings.parquet' h
        JOIN _top t ON h.company_number = t.company_number
      ) s
    `);

    // ── Phase 4: points table with explicit 0-based sequential index ──
    await conn.query(`
      CREATE OR REPLACE TABLE _points AS
      SELECT row_number() OVER (ORDER BY company_number) - 1 AS _seq,
             idx, 'c' || company_number AS id, name, 'company' AS type, status
      FROM _comp_map
      UNION ALL
      SELECT (SELECT COUNT(*) FROM _comp_map) + row_number() OVER (ORDER BY shareholder_name) - 1 AS _seq,
             idx, 's' || shareholder_name AS id, shareholder_name AS name, 'shareholder' AS type, NULL AS status
      FROM _sh_map
    `);

    // ── Phase 5: links table via numeric-indexed hash joins ──
    await conn.query(`
      CREATE OR REPLACE TABLE _links AS
      SELECT si.idx AS sourceidx, ci.idx AS targetidx,
             's' || h.shareholder_name AS source,
             'c' || h.company_number AS target
      FROM 'holdings.parquet' h
      JOIN _top t ON h.company_number = t.company_number
      JOIN _comp_map ci ON ci.company_number = h.company_number
      JOIN _sh_map si ON si.shareholder_name = h.shareholder_name
    `);

    // ── Phase 6: stats ──

    const [metaRow] = tableToObjects(await conn.query(`
      SELECT
        (SELECT COUNT(*) FROM _points) AS node_count,
        (SELECT COUNT(*) FROM _links) AS link_count,
        (SELECT COUNT(*) FROM _points WHERE type = 'company') AS company_count,
        (SELECT COUNT(*) FROM _points WHERE type = 'shareholder') AS shareholder_count
    `));
    updateStats(metaRow);

    // ── Phase 7: Cosmograph via JS objects from Arrow columns ──
    closePanel();
    if (cosmograph) {
      cosmograph.destroy();
      cosmograph = null;
    }

    // Check WebGL float texture support (requires EXT_color_buffer_float)
    const probeCanvas = document.createElement("canvas");
    probeCanvas.width = 2;
    probeCanvas.height = 2;
    probeCanvas.style.display = "none";
    container.appendChild(probeCanvas);
    const probeGl = probeCanvas.getContext("webgl2");
    const hasFloatRender = !!probeGl?.getExtension("EXT_color_buffer_float");
    container.removeChild(probeCanvas);
    if (!hasFloatRender) {
      showStatus(
        "Your browser/GPU doesn't support rendering to float textures (EXT_color_buffer_float), "
        + "which Cosmograph requires. Please try Chrome instead of Firefox, "
        + "or update your graphics drivers.",
        true,
      );
      return;
    }

    // Export points via column arrays (fast bulk copy, no cell-by-cell)
    const ptsTable = await conn.query("SELECT _seq, idx, id, name, type, status FROM _points ORDER BY _seq");
    const seqA = ptsTable.getChild("_seq").toArray();
    const idxA = ptsTable.getChild("idx").toArray();
    const idA = ptsTable.getChild("id").toArray();
    const nameA = ptsTable.getChild("name").toArray();
    const typeA = ptsTable.getChild("type").toArray();
    const nodes = new Array(seqA.length);
    const nById = new Map();
    for (let i = 0; i < seqA.length; i++) {
      const n = { idx: Number(idxA[i]), id: idA[i], name: nameA[i], type: typeA[i] };
      nodes[Number(seqA[i])] = n;
      nById.set(n.id, n);
    }
    allNodes = nodes;
    nodeById = nById;

    // Export links via column arrays
    const lnkTable = await conn.query("SELECT sourceidx, targetidx, source, target FROM _links");
    const siA = lnkTable.getChild("sourceidx").toArray();
    const tiA = lnkTable.getChild("targetidx").toArray();
    const sA = lnkTable.getChild("source").toArray();
    const tA = lnkTable.getChild("target").toArray();
    const links = [];
    for (let i = 0; i < siA.length; i++) {
      links.push({ sourceidx: Number(siA[i]), targetidx: Number(tiA[i]), source: sA[i], target: tA[i], weight: 1 });
    }

    cosmograph = new Cosmograph(container, {
      ...buildCosmographConfig(),
      points: nodes,
      links: links,
      onPointClick: (i, pos, ev) => navigateTo(i),
    });

    legendContainer.innerHTML = "";
    legend = new CosmographTypeColorLegend(cosmograph, legendContainer, {
      accessor: "type",
      items: [
        { label: "Shareholder", color: SHAREHOLDER_COLOR, value: "shareholder" },
        { label: "Company", color: COMPANY_COLOR, value: "company" },
      ],
    });

    searchContainer.innerHTML = "";
    search = new CosmographSearch(cosmograph, searchContainer, {
      accessor: "name",
    });

    showStatus(`Ready — ${metaRow.node_count.toLocaleString()} nodes, ${metaRow.link_count.toLocaleString()} edges`, false);
  } catch (err) {
    showStatus(`Error: ${err.message}`, true);
    console.error(err);
  } finally {
    if (conn) {
      await conn.close();
    }
  }
}

let debounceTimer;

function debounceReload() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(loadGraph, 400);
}

refreshBtn.addEventListener("click", loadGraph);

limitSlider.addEventListener("input", () => {
  const val = parseInt(limitSlider.value, 10);
  limitValue.textContent = val >= totalCompanies ? "All" : val.toLocaleString();
  debounceReload();
});

async function loadIndustryCodes() {
  if (!db) return;
  let conn;
  try {
    conn = await db.connect();
    const table = await conn.query(
      "SELECT code, description FROM 'industry_codes.parquet' ORDER BY description"
    );
    const rows = tableToObjects(table);
    const datalist = document.getElementById("industry-list");
    datalist.innerHTML = "";
    for (const row of rows) {
      const opt = document.createElement("option");
      opt.value = row.description;
      datalist.appendChild(opt);
      industryCodeMap.set(row.description, row.code);
    }
  } catch (err) { console.error("loadIndustryCodes error:", err); } finally {
    if (conn) await conn.close();
  }
}

statusFilter.addEventListener("change", debounceReload);
industryFilter.addEventListener("change", debounceReload);
minConnections.addEventListener("change", debounceReload);

(async () => {
  db = await initDuckDB();
  if (db) {
    await fetchTotals();
    await loadIndustryCodes();
    await loadGraph();
  }
})();

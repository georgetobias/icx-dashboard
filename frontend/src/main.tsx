import React, { useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
const Plot = React.lazy(() => import("react-plotly.js"));
import { toPng } from "html-to-image";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Download,
  FileUp,
  Gauge,
  Home,
  Maximize2,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Table2,
  X
} from "lucide-react";
import { AnalysisLevel, AppSettings, DemographicChart, DemographicRow, getJson, GroupProfile, HomeSummary, Perspective, postJson, Status, SummaryRow } from "./api";
import { uploadFile } from "./api";
import "./styles.css";
import "@fontsource-variable/dm-sans/index.css";
import { startBrowserSession } from "./session";

const nav = [
  { id: "home", label: "Home", icon: Home },
  { id: "group", label: "Group Profile", icon: Gauge },
  { id: "blue", label: "BLUE Breakdown", icon: BarChart3 },
  { id: "qa", label: "Data QA", icon: ShieldCheck },
  { id: "settings", label: "Settings", icon: Settings },
];

const freqKeys = [
  ["Daily", "Daily"],
  ["Weekly", "Weekly"],
  ["Monthly", "Monthly"],
  ["Quarterly", "Quarterly"],
  ["Annual", "Annual"],
  ["Ad hoc / Upon request", "Ad Hoc / Upon Request"]
];
const critKeys = [
  ["Very Critical", "Very Critical"],
  ["Critical", "Critical"],
  ["Somewhat Critical", "Somewhat Critical"],
  ["Not Critical", "Not Critical"]
];
const analysisOptions: Array<[AnalysisLevel, string]> = [
  ["groups", "Group Chart"],
  ["service_clusters", "Services"],
  ["division_only", "Division Only"],
  ["territory_only", "Territory Only"],
  ["division_territory", "Division + Territory"]
];
const dataGroupAnalysisOptions: Array<[AnalysisLevel, string]> = [
  ["service_clusters", "Services"],
  ["division_only", "Divisions"]
];
const DATA_GROUP_LABEL = "Data Group (Special)";
const blueBands = ["Exceptional", "Uplifted", "Leveled", "Busted"];

function fmt(value: unknown, digits = 1): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number.isFinite(value) ? value.toFixed(digits) : "-";
  return String(value);
}

function pct(value: unknown): string {
  return `${fmt(value, 1)}%`;
}

function displayCategory(value: unknown): string {
  const text = String(value ?? "Not Provided");
  const replacements: Record<string, string> = {
    "Ad hoc / Upon request": "Ad Hoc / Upon Request",
    "Other / Missing": "Other / Missing",
    "Very Critical": "Very Critical",
    "Somewhat Critical": "Somewhat Critical",
    "Not Critical": "Not Critical",
  };
  return replacements[text] ?? text;
}

function useHomeSummary(perspective: Perspective, refreshKey = 0) {
  const [data, setData] = useState<HomeSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    getJson<HomeSummary>(`/api/home-summary?perspective=${perspective}`)
      .then((value) => { if (active) setData(value); })
      .catch((err) => { if (active) { setData(null); setError(err.message); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [perspective, refreshKey]);
  return { data, error, loading };
}

function StatusPill({ status }: { status?: Status }) {
  if (!status) return null;
  const ok = Boolean(status.ok);
  return (
    <div className={`status-pill ${ok ? "ok" : "bad"}`} title={status.source}>
      {ok ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
      <span>{ok ? "Data check passed" : "Data check issue"}</span>
      {status.rows ? <b>{status.rows.toLocaleString()} rows</b> : null}
    </div>
  );
}

function ExportButton() {
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  async function exportPng() {
    const node = document.getElementById("page-export");
    if (!node) return;
    setExporting(true);
    setError("");
    try {
    const dataUrl = await toPng(node, {
      cacheBust: true,
      pixelRatio: 2,
      backgroundColor: node.closest(".dark-mode") ? "#0b1b32" : "#F5F8FF",
      filter: (element) => !element.classList?.contains("no-export")
    });
    const link = document.createElement("a");
    const today = new Date();
    const localDate = [
      today.getFullYear(),
      String(today.getMonth() + 1).padStart(2, "0"),
      String(today.getDate()).padStart(2, "0"),
    ].join("-");
    link.download = `icx-dashboard-${localDate}.png`;
    link.href = dataUrl;
    link.click();
    } catch {
      setError("Export failed. Try a smaller view or a chart’s download button.");
    } finally { setExporting(false); }
  }
  return (
    <><button className="icon-button no-export" disabled={exporting} onClick={exportPng} title="Export current view as PNG">
      <Download size={18} />
      {exporting ? "Exporting…" : "Export PNG"}
    </button>
    {error && <span role="alert">{error}</span>}</>
  );
}

function Shell() {
  const [page, setPage] = useState("home");
  const [perspective, setPerspective] = useState<Perspective>("provider");
  const [selectedGroup, setSelectedGroup] = useState<string>("All Groups");
  const [darkMode, setDarkMode] = useState(false);
  const [dataRefreshKey, setDataRefreshKey] = useState(0);
  useEffect(() => {
    let revision = "";
    let active = true;
    const check = async () => {
      try {
        const result = await getJson<{ revision: string }>("/api/source-revision");
        if (!active) return;
        if (revision && result.revision !== revision) setDataRefreshKey((value) => value + 1);
        revision = result.revision;
      } catch { /* Visible page requests provide the error state. */ }
    };
    void check();
    const timer = setInterval(check, 5000);
    window.addEventListener("focus", check);
    return () => { active = false; clearInterval(timer); window.removeEventListener("focus", check); };
  }, []);
  const { data, error, loading } = useHomeSummary(perspective, dataRefreshKey);
  const [allProfileGroups, setAllProfileGroups] = useState<string[]>([]);
  useEffect(() => {
    let active = true;
    Promise.all([getJson<{groups: string[]}>("/api/groups?perspective=provider"), getJson<{groups: string[]}>("/api/groups?perspective=customer")])
      .then(([provider, customer]) => { if (active) setAllProfileGroups([...new Set([...provider.groups, ...customer.groups])].filter((name) => name !== "All Groups").sort()); })
      .catch(() => { /* The main data request displays source errors. */ });
    return () => { active = false; };
  }, [dataRefreshKey]);
  const groups = useMemo(() => ["All Groups", ...(data?.rows.map((row) => row.group_name) ?? [])], [data]);
  const profileGroups = useMemo(
    () => ["All Groups", ...allProfileGroups],
    [allProfileGroups]
  );
  const selectedRealGroup = groups.includes(selectedGroup) ? selectedGroup : "All Groups";

  return (
    <div className={`app-shell ${darkMode ? "dark-mode" : ""}`}>
      <aside className="sidebar no-export">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true">
            <BarChart3 size={32} />
          </div>
          <div>
            <h1>Internal CX</h1>
            <p>Synthetic Data Demo</p>
          </div>
        </div>
        <nav>
          {nav.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={page === item.id ? "active" : ""} onClick={() => setPage(item.id)}>
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </nav>
        <div className="privacy-note">
          The included demo is entirely synthetic. Imported data stays on this computer. Update the master CSV in Settings; imported data is saved for the next launch.
        </div>
      </aside>
      <main>
        <header className="topbar no-export">
          <div>
            <h2>iCX Dashboard</h2>
          </div>
          <StatusPill status={data?.status} />
          <ExportButton />
        </header>
        <section id="page-export" className="page-card">
          {page === "settings" && <SettingsPage darkMode={darkMode} setDarkMode={setDarkMode} onDataSourceChange={() => setDataRefreshKey((value) => value + 1)} />}
          {page !== "settings" && loading ? <Loading /> : null}
          {page !== "settings" && error ? <><ErrorPanel message={error} /><button className="small-button" onClick={() => setPage("settings")}>Open CSV Settings</button></> : null}
          {data && page !== "settings" && (
            <>
              {page === "home" && (
                <HomePage
                  data={data}
                  perspective={perspective}
                  setPerspective={setPerspective}
                  selectedGroup={selectedRealGroup}
                  setSelectedGroup={setSelectedGroup}
                />
              )}
              {page === "group" && (
                <GroupPage
                  key={dataRefreshKey}
                  group={profileGroups.includes(selectedGroup) ? selectedGroup : "All Groups"}
                  groups={profileGroups}
                  setGroup={setSelectedGroup}
                />
              )}
              {page === "blue" && <BlueBreakdownPage key={dataRefreshKey} data={data} perspective={perspective} setPerspective={setPerspective} groups={groups} selectedGroup={selectedRealGroup} setSelectedGroup={setSelectedGroup} />}
              {page === "qa" && <QaPage key={dataRefreshKey} />}
            </>
          )}
        </section>
      </main>
    </div>
  );
}

function Loading() {
  return (
    <div className="loading">
      <RefreshCw size={20} className="spin" />
      Loading iCX data...
    </div>
  );
}

function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="empty-state">
      <AlertTriangle size={24} />
      <h3>App could not load the data.</h3>
      <p>{message}</p>
    </div>
  );
}

function HomePage(props: {
  data: HomeSummary;
  perspective: Perspective;
  setPerspective: (value: Perspective) => void;
  selectedGroup: string;
  setSelectedGroup: (value: string) => void;
}) {
  const { data, perspective, setPerspective, selectedGroup, setSelectedGroup } = props;
  const [query, setQuery] = useState("");
  const rows = useMemo(() => {
    return data.rows.filter((row) => {
      const matchesGroup = selectedGroup === "All Groups" || row.group_name === selectedGroup;
      const matchesQuery = row.group_name.toLowerCase().includes(query.toLowerCase()) || row.group_code.toLowerCase().includes(query.toLowerCase());
      return matchesGroup && matchesQuery;
    });
  }, [data.rows, query, selectedGroup]);
  const attentionExample = data.rows.find((row) => Number.isFinite(Number(row.avg_criticality)));

  return (
    <>
      <section className="hero-grid">
        <div>
          <h2>Executive Overview</h2>
          <p>
            This page summarizes per-group-performance, service coverage, frequency mix,
            criticality mix, and attention scores.
          </p>
        </div>
        <MetricTile label="Overall Internal CX Dashboard" value={fmt(data.tiles.overall_icx, 1)} detail={`${data.tiles.total_ratings?.toLocaleString?.() ?? "-"} Scored Ratings`} />
        <MetricTile label="Groups" value={fmt(data.tiles.groups, 0)} detail={`${data.tiles.small_n_groups ?? 0} Small-N Groups`} />
      </section>
      <section className="control-row no-export">
        <div className="segmented">
          <button className={perspective === "provider" ? "active" : ""} onClick={() => setPerspective("provider")}>Service Provider</button>
          <button className={perspective === "customer" ? "active" : ""} onClick={() => setPerspective("customer")}>Internal Customer</button>
        </div>
        <label className="select-label">
          Group
          <select value={selectedGroup} onChange={(event) => setSelectedGroup(event.target.value)}>
            <option>All Groups</option>
            {data.rows.map((row) => <option key={row.group_name}>{row.group_name}</option>)}
          </select>
        </label>
        <label className="search-box">
          <Search size={16} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search group" />
        </label>
      </section>
      <ExecutiveTable rows={rows} />
      {attentionExample ? <AttentionFormula row={attentionExample} /> : null}
    </>
  );
}

function MetricTile({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="metric-tile">
      <span>{label}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
    </div>
  );
}

function MixBar({ row }: { row: SummaryRow }) {
  const parts = [
    ["Busted", row.busted_pct, "busted"],
    ["Leveled", row.leveled_pct, "leveled"],
    ["Uplifted", row.uplifted_pct, "uplifted"],
    ["Exceptional", row.exceptional_pct, "exceptional"]
  ] as const;
  return (
    <div className="mixbar" title={`B ${row.busted} · L ${row.leveled} · U ${row.uplifted} · E ${row.exceptional}`}>
      {parts.map(([label, value, klass]) => (
        <span key={label} className={klass} style={{ width: `${Math.max(0, Number(value))}%` }}>
          {Number(value) >= 12 ? `${Math.round(Number(value))}%` : ""}
        </span>
      ))}
    </div>
  );
}

function AttentionFormula({ row }: { row: SummaryRow }) {
  const nps = Number(row.nps);
  const ratings = Number(row.ratings);
  const avgCriticality = Number(row.avg_criticality);
  const gap = Math.max(100 - nps, 0);
  const volume = Math.log(1 + ratings);
  const criticality = avgCriticality / 4;
  const score = gap * volume * criticality;
  return (
    <section className="formula-panel formula-visual">
      <div>
        <h3>Attention Score Formula</h3>
        <p className="math-line">max(100 - iCX, 0) x ln(1 + Responses) x (Avg Criticality / 4)</p>
      </div>
      <div className="math-computation" aria-label="Attention Score Example">
        <MathStep label="iCX Gap" value={`max(100 - ${nps.toFixed(1)}, 0) = ${gap.toFixed(1)}`} />
        <span className="math-operator">x</span>
        <MathStep label="Response Weight" value={`ln(1 + ${ratings.toLocaleString()}) = ${volume.toFixed(2)}`} />
        <span className="math-operator">x</span>
        <MathStep label="Criticality Weight" value={`${avgCriticality.toFixed(2)} / 4 = ${criticality.toFixed(2)}`} />
        <span className="math-operator">=</span>
        <MathStep label="Example Score" value={score.toFixed(0)} strong />
      </div>
      <p>
        This example uses the active dataset: lower scores, higher rating volume, and higher criticality increase priority.
      </p>
    </section>
  );
}

function MathStep({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className={`math-step ${strong ? "result" : ""}`}>
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}

function ExecutiveTable({ rows }: { rows: SummaryRow[] }) {
  return (
    <section className="table-panel">
      <div className="section-heading">
        <Table2 size={20} />
        <div>
          <h3>organization Groups Table</h3>
          <p>Scores, Rating Volume, Defined Services, Frequency, Criticality, And Attention Score.</p>
        </div>
      </div>
      <div className="table-scroll">
        <table className="score-table">
          <thead>
            <tr>
              <th>Group</th>
              <th>iCX Score</th>
              <th>Ratings</th>
              <th>Services</th>
              <th>Frequency</th>
              <th>Criticality</th>
              <th>Attention Score</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.group_name}>
                <td>
                  <strong>{row.group_code}</strong>
                  <span>{row.group_name}</span>
                </td>
                <td className="score">{fmt(row.nps, 1)}</td>
                <td>{row.ratings.toLocaleString()}{row.small_n ? <em className="flag">Small-N</em> : null}</td>
                <td className="service-number">{row.defined_service_clusters.toLocaleString()}</td>
                <td><MiniPercents row={row} prefix="frequency_pct_" items={freqKeys} /></td>
                <td><MiniPercents row={row} prefix="criticality_pct_" items={critKeys} /></td>
                <td className="attention">{fmt(row.attention_score, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function MiniPercents({ row, prefix, items }: { row: SummaryRow; prefix: string; items: string[][] }) {
  return (
    <div className="mini-percents">
      {items.map(([key, label]) => (
        <span key={key}><b>{label}</b>{pct(row[`${prefix}${key}`])}</span>
      ))}
    </div>
  );
}

function GroupPage({ group, groups, setGroup }: { group: string; groups: string[]; setGroup: (value: string) => void }) {
  const [profile, setProfile] = useState<GroupProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [perspective, setPerspective] = useState<Perspective>("provider");
  const [analysis, setAnalysis] = useState<AnalysisLevel>("groups");
  const [scatterSize, setScatterSize] = useState(105);
  const [showLabels, setShowLabels] = useState(true);
  const [meanLine, setMeanLine] = useState(true);
  const [fullLabels, setFullLabels] = useState(false);
  const [editLabels, setEditLabels] = useState(false);
  const [minRatings, setMinRatings] = useState(5);
  const isSynthetic = group === DATA_GROUP_LABEL;
  const effectiveAnalysis: AnalysisLevel = isSynthetic && !["service_clusters", "division_only"].includes(analysis)
    ? "service_clusters"
    : analysis;
  useEffect(() => {
    if (!group) return;
    let active = true;
    setProfile(null);
    setError(null);
    getJson<GroupProfile>(`/api/group/${encodeURIComponent(group)}`)
      .then((value) => { if (active) setProfile(value); })
      .catch((err) => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [group]);
  useEffect(() => {
    if (!isSynthetic) return;
    setPerspective("provider");
    setAnalysis("service_clusters");
    setMinRatings(1);
  }, [isSynthetic]);
  if (error) return <ErrorPanel message={error} />;
  if (!profile) return <Loading />;
  const received = profile.received ?? {};
  const gave = profile.gave ?? {};
  const interIntra = profile.inter_intra ?? {};
  return (
    <>
      <section className="control-row no-export">
        <label className="select-label">
          Group
          <select value={group} onChange={(event) => setGroup(event.target.value)}>
            {groups.map((item) => <option key={item}>{item}</option>)}
          </select>
        </label>
        {isSynthetic ? (
          <div className="synthetic-view-label">Synthetic Provider View</div>
        ) : (
          <div className="segmented">
            <button className={perspective === "provider" ? "active" : ""} onClick={() => setPerspective("provider")}>Service Provider</button>
            <button className={perspective === "customer" ? "active" : ""} onClick={() => setPerspective("customer")}>Internal Customer</button>
          </div>
        )}
        <label className="select-label">Analysis<select value={effectiveAnalysis} onChange={(event) => setAnalysis(event.target.value as AnalysisLevel)}>{(isSynthetic ? dataGroupAnalysisOptions : analysisOptions).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="select-label compact">Min Ratings<input type="number" min={1} max={100} value={minRatings} onChange={(event) => setMinRatings(Math.max(1, Math.min(100, Number(event.target.value) || 1)))} /></label>
        <label className="select-label compact">Size<input type="range" min={85} max={125} step={5} value={scatterSize} onChange={(event) => setScatterSize(Number(event.target.value))} /></label>
        <label className="toggle-label"><input type="checkbox" checked={showLabels} onChange={(event) => setShowLabels(event.target.checked)} />Labels</label>
        <label className="toggle-label"><input type="checkbox" checked={meanLine} onChange={(event) => setMeanLine(event.target.checked)} />Mean Line</label>
        <label className="toggle-label"><input type="checkbox" checked={fullLabels} onChange={(event) => setFullLabels(event.target.checked)} />Full Labels</label>
        <label className="toggle-label"><input type="checkbox" checked={editLabels} onChange={(event) => setEditLabels(event.target.checked)} />Edit Labels</label>
      </section>
      <section className="profile-header">
        <div>
          <span className="eyebrow">Group Profile</span>
          <h2>{profile.group_name}</h2>
        </div>
        {isSynthetic ? (
          <>
            <MetricTile label="Aggregate iCX" value={fmt(received.nps, 1)} detail={`${fmt(received.ratings, 0)} Source Ratings`} />
            <MetricTile label="Avg Criticality" value={fmt(received.avg_criticality, 2)} detail="Workbook Rating Rows" />
            <MetricTile label="Services" value={fmt(received.services, 0)} detail="Usable Service Buckets" />
            <MetricTile label="Divisions" value={fmt(received.divisions, 0)} detail="Owner-Defined Data Divisions" />
          </>
        ) : (
          <>
            <MetricTile label="Received iCX" value={fmt(received.nps, 1)} detail={`${fmt(received.ratings, 0)} Provider Ratings`} />
            <MetricTile label="Gave iCX" value={fmt(gave.nps, 1)} detail={`${fmt(gave.ratings, 0)} Customer Ratings`} />
            <MetricTile label="Received - Gave" value={fmt(profile.disparity, 1)} detail="Perception Gap, Not Blame" />
            <MetricTile label="Intra" value={pct(interIntra.intra_pct)} detail={`${fmt(interIntra.intra_n, 0)} Same-Group Ratings`} />
            <MetricTile label="Inter" value={pct(interIntra.inter_pct)} detail={`${fmt(interIntra.inter_n, 0)} Cross-Group Ratings`} />
            <MetricTile label="Inter - Intra" value={fmt(interIntra.gap, 1)} detail={`Inter ${fmt(interIntra.inter_nps, 1)} Vs Intra ${fmt(interIntra.intra_nps, 1)}`} />
          </>
        )}
      </section>
      {isSynthetic ? (
        <section className="synthetic-data-group-note">
          <strong>Special analytical cohort</strong>
          <p>{profile.profile_note}</p>
        </section>
      ) : <GroupComparisonTable selectedGroup={group} rows={profile.comparison} />}
      <ChartPage
        title={isSynthetic
          ? `${effectiveAnalysis === "division_only" ? "Data Group Divisions" : "Data Group Services"}: iCX vs Criticality`
          : effectiveAnalysis === "territory_only" && group === "All Groups"
            ? "Territories: iCX vs Criticality"
            : "iCX vs Criticality"}
        view="criticality-scatter"
        perspective={perspective}
        group={group}
        analysis={effectiveAnalysis}
        minRatings={minRatings}
        showLabels={showLabels}
        fullLabels={fullLabels}
        meanLine={meanLine}
        scatterSize={scatterSize / 100}
        editLabels={editLabels}
        embedded
      />
      {!isSynthetic ? <DemographicCharts charts={profile.demographics ?? []} /> : null}
      {!isSynthetic ? (
        <>
          <section className="split-tables">
            <div>
              <ChartPage title="Received - Gave Gap" view="received-gave-gap" perspective="provider" group={group} embedded />
              <GapExplanation title="Received - Gave" text="This compares how a group is rated as a service provider against how that same group rates the services it receives. Positive means the group receives stronger ratings than it gives; negative means it receives weaker ratings than it gives." />
            </div>
            <div>
              <ChartPage title="Inter - Intra Gap" view="inter-intra-gap" perspective="provider" group={group} embedded />
              <GapExplanation title="Inter - Intra" text="This compares ratings from other groups against ratings from the same group. Positive means external/internal-customer ratings are stronger than own-group ratings; negative means external ratings are weaker." />
            </div>
          </section>
          <ChartPage title="Frequency Attention Queue" view="frequency-attention" perspective={perspective} group={group} embedded />
        </>
      ) : null}
    </>
  );
}

function demographicLabel(label: string): string {
  return label.replace(/ years old$/, "");
}

function DemographicCharts({ charts }: { charts: DemographicChart[] }) {
  const visibleCharts = charts.filter((chart) => chart.rows.length > 0);
  if (!visibleCharts.length) return null;
  return (
    <section className="demographics-panel">
      <div className="section-heading">
        <BarChart3 size={20} />
        <div>
          <h3>Respondent Demographics</h3>
          <p>Unique respondents in the selected group, shown as share and count.</p>
        </div>
      </div>
      <div className="demographics-grid">
        {visibleCharts.map((chart) => <DemographicCard key={chart.key} chart={chart} />)}
      </div>
    </section>
  );
}

function DemographicCard({ chart }: { chart: DemographicChart }) {
  const maxPct = Math.max(...chart.rows.map((row) => row.pct), 1);
  return (
    <article className="demographic-card">
      <div className="demographic-card-header">
        <h4>{chart.title}</h4>
        <span>{chart.total.toLocaleString()} respondents</span>
      </div>
      <div className="demographic-list" role="list" aria-label={chart.title}>
        {chart.rows.map((row: DemographicRow) => {
          const relativeWidth = Math.max(2, (row.pct / maxPct) * 100);
          return (
            <div className="demographic-row" role="listitem" key={row.label}>
              <span className="demographic-label" title={row.label}>{demographicLabel(row.label)}</span>
              <div className="demographic-track" aria-hidden="true">
                <span className="demographic-stem" style={{ width: `${relativeWidth}%` }}>
                  <span className="demographic-dot" />
                </span>
              </div>
              <strong className="demographic-pct">{pct(row.pct)}</strong>
              <span className="demographic-count">{row.count.toLocaleString()}</span>
            </div>
          );
        })}
      </div>
      <p className="demographic-footnote">Share of unique respondents</p>
    </article>
  );
}

function GapExplanation({ title, text }: { title: string; text: string }) {
  return (
    <div className="gap-explanation">
      <b>{title}</b>
      <p>{text}</p>
    </div>
  );
}

function GroupComparisonTable({ selectedGroup, rows }: { selectedGroup: string; rows: any[] }) {
  const allGroups = selectedGroup === "All Groups";
  return (
    <section className="table-panel">
      <div className="section-heading">
        <Table2 size={20} />
        <div>
          <h3>{allGroups ? "All Groups Provider Comparison" : "Selected Group Vs All Other Groups"}</h3>
          <p>
            {allGroups
              ? "Provider iCX, Rating Volume, Frequency, And Criticality, Compared With The Overall Provider Score."
              : `Provider iCX, Dominant Frequency, And Average Criticality, With ${selectedGroup} Highlighted.`}
          </p>
        </div>
      </div>
      <div className="table-scroll comparison-scroll">
        <table className="score-table comparison-table">
          <thead><tr><th>Group</th><th>iCX</th><th>Ratings</th><th>Dominant Frequency</th><th>Avg Criticality</th><th>{allGroups ? "Gap Vs Overall" : "Gap Vs Selected"}</th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={String(row.label_full)} className={row.selected ? "selected-row" : ""}>
                <td><strong>{String(row.label_short ?? "-")}</strong><span>{String(row.label_full ?? "-")}</span></td>
                <td className="score">{fmt(row.nps, 1)}</td>
                <td>{fmt(row.ratings, 0)}</td>
                <td>{displayCategory(row.dominant_frequency ?? "-")}</td>
                <td>{fmt(row.avg_criticality, 2)}</td>
                <td>{fmt(row.gap_vs_selected, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SmallSummaryTable({ title, rows }: { title: string; rows: any[] }) {
  return (
    <div className="mini-table-card">
      <h3>{title}</h3>
      <table>
        <thead><tr><th>Item</th><th>iCX</th><th>Ratings</th><th>Attention</th></tr></thead>
        <tbody>
          {rows.slice(0, 8).map((row, index) => (
            <tr key={`${row.label_full ?? row.group ?? index}`}>
              <td>{String(row.label_full ?? row.group ?? row.service_cluster ?? "-")}</td>
              <td>{fmt(row.nps, 1)}</td>
              <td>{fmt(row.ratings, 0)}</td>
              <td>{fmt(row.attention_score, 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChartPage({
  title,
  view,
  perspective,
  group,
  analysis = "groups",
  minRatings = 1,
  showLabels = true,
  fullLabels = false,
  meanLine = true,
  scatterSize = 1.05,
  editLabels = false,
  band,
  embedded = false
}: {
  title: string;
  view: string;
  perspective: Perspective;
  group: string;
  analysis?: AnalysisLevel;
  minRatings?: number;
  showLabels?: boolean;
  fullLabels?: boolean;
  meanLine?: boolean;
  scatterSize?: number;
  editLabels?: boolean;
  band?: string;
  embedded?: boolean;
}) {
  const [payload, setPayload] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const isAttentionQueue = ["frequency-attention", "blue-attention-queue"].includes(view);
  const chartHeight = view === "frequency-attention" ? 940 : view === "blue-attention-queue" ? 620 : view.includes("gap") ? 520 : view === "criticality-scatter" ? 680 : 540;
  const fullscreenHeight = view === "criticality-scatter" ? 820 : 760;
  const canFullscreen = view.includes("scatter");
  const panelClass = [
    "chart-panel",
    embedded ? "embedded" : "",
    view.includes("gap") ? "gap-chart" : "",
    view === "criticality-scatter" ? "scatter-chart" : "",
    ["blue-attention-queue", "frequency-attention"].includes(view) ? "queue-chart" : ""
  ].filter(Boolean).join(" ");
  useEffect(() => {
    let active = true;
    setPayload(null);
    setError(null);
    const params = new URLSearchParams({
      perspective,
      group,
      analysis,
      min_ratings: String(minRatings),
      show_labels: String(showLabels),
      full_labels: String(fullLabels),
      mean_line: String(meanLine),
      scatter_size: String(scatterSize),
      band: band ?? "Busted"
    });
    getJson<any>(`/api/chart/${view}?${params.toString()}`)
      .then((nextPayload) => {
        if (active) setPayload(nextPayload);
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [view, perspective, group, analysis, minRatings, showLabels, fullLabels, meanLine, scatterSize, band]);
  useEffect(() => {
    if (!fullscreen) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setFullscreen(false);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [fullscreen]);
  if (error) return <ErrorPanel message={error} />;
  const plotConfig = {
    responsive: true,
    displaylogo: false,
    editable: editLabels,
    edits: { annotationPosition: editLabels, annotationTail: editLabels }
  };
  const renderPlot = (height: number, fullscreenMode = false) => (
    <React.Suspense fallback={<Loading />}><Plot
      data={payload.figure.data}
      layout={{ ...payload.figure.layout, autosize: true, height }}
      config={plotConfig}
      useResizeHandler
      className={`plotly-chart ${fullscreenMode ? "fullscreen-plot" : ""}`}
      style={{ height }}
    /></React.Suspense>
  );
  return (
    <section className={panelClass}>
      <div className="chart-heading-row">
        <div className="section-heading">
          <BarChart3 size={20} />
          <div>
            <h3>{title}</h3>
            <p>{view === "frequency-attention"
              ? "Attention Score combines iCX gap, response volume, and criticality. " + (perspective === "provider" ? "Service Provider" : "Internal Customer") + " Perspective | " + group
              : (perspective === "provider" ? "Service Provider" : "Internal Customer") + " Perspective | " + group}</p>
          </div>
        </div>
        {canFullscreen && payload ? (
          <button className="icon-button chart-fullscreen-button no-export" onClick={() => setFullscreen(true)} title="Open Scatterplot Fullscreen">
            <Maximize2 size={17} />
            Fullscreen
          </button>
        ) : null}
      </div>
      {!payload ? <Loading /> : isAttentionQueue ? <AttentionQueue rows={payload.rows ?? []} defaultBand={band} /> : renderPlot(chartHeight)}
      {fullscreen && payload ? (
        <div className="fullscreen-backdrop no-export" role="dialog" aria-modal="true" aria-label={`${title} Fullscreen`}>
          <div className="fullscreen-chart-panel">
            <div className="fullscreen-chart-header">
              <div>
                <span className="eyebrow">Fullscreen Scatterplot</span>
                <h3>{title}</h3>
                <p>{perspective === "provider" ? "Service Provider" : "Internal Customer"} Perspective | {group}</p>
              </div>
              <button className="icon-button" onClick={() => setFullscreen(false)} title="Close Fullscreen Scatterplot">
                <X size={18} />
                Close
              </button>
            </div>
            {renderPlot(fullscreenHeight, true)}
          </div>
        </div>
      ) : null}
    </section>
  );
}

type AttentionQueueRow = {
  label_full?: string;
  label_short?: string;
  frequency_normalized?: string;
  dominant_frequency?: string;
  service_cluster_display?: string;
  service_cluster?: string;
  ratings?: number;
  nps?: number;
  avg_criticality?: number | null;
  attention_score?: number;
  icx_score_band?: string;
};

const attentionBandColors: Record<string, string> = {
  Busted: "#D92D20",
  Leveled: "#B6E880",
  Uplifted: "#0E7A5F",
  Exceptional: "#155EEF",
};

function AttentionQueue({ rows, defaultBand }: { rows: AttentionQueueRow[]; defaultBand?: string }) {
  if (!rows.length) return <div className="attention-queue-empty">No rows match the selected attention filters.</div>;
  const maxAttention = Math.max(...rows.map((row) => Number(row.attention_score ?? 0)), 1);
  return (
    <div className="attention-queue-card">
      <div className="attention-queue-summary">
        <span>{rows.length} prioritized {rows.length === 1 ? "row" : "rows"}</span>
        <span>Higher priority →</span>
      </div>
      <div className="attention-queue-list" role="list" aria-label="Attention queue">
        {rows.map((row, index) => {
          const score = Number(row.attention_score ?? 0);
          const band = row.icx_score_band || defaultBand || "Uplifted";
          const color = attentionBandColors[band] ?? attentionBandColors.Uplifted;
          const label = row.service_cluster_display || row.label_full || row.service_cluster || row.label_short || "-";
          const secondary = row.frequency_normalized || row.dominant_frequency || "";
          const width = (score / maxAttention) * 100;
          return (
            <div className="attention-queue-row" role="listitem" key={`${label}-${secondary}-${index}`}>
              <div className="attention-queue-label">
                <strong>{label}</strong>
                <span>{displayCategory(secondary)}{row.ratings !== undefined ? ` · ${row.ratings.toLocaleString()} ${row.ratings === 1 ? "response" : "responses"}` : ""}</span>
              </div>
              <div className="attention-queue-track" aria-hidden="true">
                <span className="attention-queue-stem" style={{ width: `${width}%`, backgroundColor: color }}>
                  {score > 0 ? <span className="attention-queue-dot" style={{ backgroundColor: color }} /> : null}
                </span>
              </div>
              <div className="attention-queue-detail"><strong>{fmt(score, 0)}</strong><span>Attention</span></div>
              <div className="attention-queue-detail"><strong>{fmt(row.nps, 1)}</strong><span>iCX</span></div>
              <div className="attention-queue-detail"><strong>{fmt(row.avg_criticality, 2)}</strong><span>Criticality</span></div>
              <span className={`attention-band-label ${band.toLowerCase()}`} style={{ borderColor: color, color: band === "Leveled" ? "#496116" : color }}>{band}</span>
            </div>
          );
        })}
      </div>
      <p className="demographic-footnote">Attention score combines iCX gap, response volume, and criticality.</p>
    </div>
  );
}

function BlueBreakdownPage({ data, perspective, setPerspective, groups, selectedGroup, setSelectedGroup }: { data: HomeSummary; perspective: Perspective; setPerspective: (value: Perspective) => void; groups: string[]; selectedGroup: string; setSelectedGroup: (value: string) => void }) {
  const [analysisLevel, setAnalysisLevel] = useState<"service" | "division" | "territory">("service");
  return (
    <>
      <section className="control-row no-export">
        <div className="segmented">
          <button className={perspective === "provider" ? "active" : ""} onClick={() => setPerspective("provider")}>Service Provider</button>
          <button className={perspective === "customer" ? "active" : ""} onClick={() => setPerspective("customer")}>Internal Customer</button>
        </div>
        <label className="select-label">Group<select value={selectedGroup} onChange={(event) => setSelectedGroup(event.target.value)}>{groups.map((g) => <option key={g}>{g}</option>)}</select></label>
        <label className="select-label">Analysis Level<select value={analysisLevel} onChange={(event) => setAnalysisLevel(event.target.value as "service" | "division" | "territory")}><option value="service">Service</option><option value="division">Division</option><option value="territory">Territory</option></select></label>
      </section>
      <BlueAnalysisBreakdown group={selectedGroup} perspective={perspective} analysis={analysisLevel} />
      {analysisLevel === "service" && selectedGroup !== "All Groups" ? <BlueServiceQueues group={selectedGroup} perspective={perspective} /> : null}
    </>
  );
}

function BlueBadge({ band }: { band: string }) {
  return <span className={`blue-label ${band.toLowerCase()}`}>{band}</span>;
}

function BlueAnalysisBreakdown({ group, perspective, analysis }: { group: string; perspective: Perspective; analysis: "service" | "division" | "territory" }) {
  const [rows, setRows] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ group, perspective, analysis });
    getJson<{ rows: any[] }>(`/api/blue-breakdown?${params.toString()}`)
      .then((payload) => { if (active) setRows(payload.rows); })
      .catch((err) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [group, perspective, analysis]);
  if (error) return <ErrorPanel message={error} />;
  if (loading) return <Loading />;
  if (analysis === "division") return <DivisionBlueBreakdown rows={rows} group={group} />;
  if (analysis === "territory") return <TerritoryBlueBreakdown rows={rows} group={group} />;
  return (
    <section className="table-panel service-breakdown-panel">
      <div className="section-heading"><Table2 size={20} /><div><h3>Service BLUE Breakdown</h3><p>{group === "All Groups" ? "All Services" : `Services For ${group}`} With BLUE Counts, iCX, Average Criticality, And Dominant Frequency.</p></div></div>
      <div className="table-scroll">
        <table className="score-table service-breakdown-table">
          <thead><tr><th>Service</th><th>Provider</th><th><BlueBadge band="Busted" /></th><th><BlueBadge band="Leveled" /></th><th><BlueBadge band="Uplifted" /></th><th><BlueBadge band="Exceptional" /></th><th>Ratings</th><th>iCX</th><th>Avg Criticality</th><th>Dominant Frequency</th></tr></thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row.service_cluster_key ?? row.label_full ?? index}`}>
                <td><strong>{String(row.service_cluster ?? row.label_full ?? "-")}</strong></td>
                <td>{String(row.provider_group ?? "-")}</td>
                <td>{fmt(row.busted, 0)}</td>
                <td>{fmt(row.leveled, 0)}</td>
                <td>{fmt(row.uplifted, 0)}</td>
                <td>{fmt(row.exceptional, 0)}</td>
                <td>{fmt(row.ratings, 0)}</td>
                <td>{fmt(row.nps, 2)}</td>
                <td>{fmt(row.avg_criticality, 2)}</td>
                <td>{String(row.dominant_frequency ?? "-")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function DivisionBlueBreakdown({ rows, group }: { rows: any[]; group: string }) {
  return (
    <section className="table-panel service-breakdown-panel">
      <div className="section-heading"><Table2 size={20} /><div><h3>Division BLUE Breakdown</h3><p>{group === "All Groups" ? "All Divisions By Group" : `Divisions For ${group}`}. Overall, Intra, And Inter iCX Use All Rating Rows In Each Division.</p></div></div>
      <div className="table-scroll">
        <table className="score-table division-breakdown-table">
          <thead><tr>{group === "All Groups" ? <th>Group</th> : null}<th>Division</th><th>Overall iCX</th><th>Intra</th><th>Inter</th><th><BlueBadge band="Busted" /></th><th><BlueBadge band="Leveled" /></th><th><BlueBadge band="Uplifted" /></th><th><BlueBadge band="Exceptional" /></th><th>Ratings</th></tr></thead>
          <tbody>{rows.map((row, index) => <tr key={`${row.group_name}-${row.division}-${index}`}>{group === "All Groups" ? <td>{String(row.group_name)}</td> : null}<td><strong>{String(row.division)}</strong></td><td>{fmt(row.overall_icx, 2)}</td><td>{fmt(row.intra_icx, 2)}</td><td>{fmt(row.inter_icx, 2)}</td><td>{fmt(row.busted, 0)}</td><td>{fmt(row.leveled, 0)}</td><td>{fmt(row.uplifted, 0)}</td><td>{fmt(row.exceptional, 0)}</td><td>{fmt(row.ratings, 0)}</td></tr>)}</tbody>
        </table>
      </div>
    </section>
  );
}

function TerritoryBlueBreakdown({ rows, group }: { rows: any[]; group: string }) {
  const allGroups = group === "All Groups";
  return (
    <section className="table-panel service-breakdown-panel">
      <div className="section-heading"><Table2 size={20} /><div><h3>Territory BLUE Breakdown</h3><p>{allGroups ? "One Rollup Per Group Rated" : `Territory-Serving Divisions For ${group}`}. Territory Rows Are Division Rated Values Containing “Serving Territory”; Territory iCX Uses Only Those Eligible Rows.</p></div></div>
      <div className="table-scroll">
        <table className="score-table territory-breakdown-table">
          <thead><tr><th>Provider Group</th><th>{allGroups ? "Territory Divisions" : "Territory (Division Rated)"}</th><th>Group iCX</th><th>Territory iCX</th><th><BlueBadge band="Busted" /></th><th><BlueBadge band="Leveled" /></th><th><BlueBadge band="Uplifted" /></th><th><BlueBadge band="Exceptional" /></th><th>Ratings</th></tr></thead>
          <tbody>{rows.map((row, index) => <tr key={`${row.group_name}-${row.territory_group}-${row.territory}-${index}`}><td><strong>{String(row.group_name)}</strong></td><td>{allGroups ? fmt(row.territory_count, 0) : String(row.territory)}</td><td>{fmt(row.group_icx, 2)}</td><td>{fmt(row.territory_icx, 2)}</td><td>{fmt(row.busted, 0)}</td><td>{fmt(row.leveled, 0)}</td><td>{fmt(row.uplifted, 0)}</td><td>{fmt(row.exceptional, 0)}</td><td>{fmt(row.ratings, 0)}</td></tr>)}</tbody>
        </table>
      </div>
    </section>
  );
}

function BlueServiceQueues({ group, perspective }: { group: string; perspective: Perspective }) {
  return (
    <section className="queue-stack">
      {blueBands.map((band) => (
        <ChartPage key={band} title={`${band} Service Attention Queue`} view="blue-attention-queue" perspective={perspective} group={group} band={band} embedded />
      ))}
    </section>
  );
}

function QaPage() {
  const [qa, setQa] = useState<any | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { getJson<any>("/api/data-qa").then(setQa).catch((err) => setError(err.message)); }, []);
  if (error) return <ErrorPanel message={error} />;
  if (!qa) return <Loading />;
  return (
    <>
      <section className="page-intro">
        <span className="eyebrow">Data QA</span>
        <h2>Guardrails and Missing-Value Checks</h2>
        <p>{qa.privacy_note}</p>
      </section>
      <div className="qa-grid">
        {Object.entries(qa.status.checks ?? {}).map(([key, value]) => (
          <div className={`qa-card ${value ? "ok" : "bad"}`} key={key}>
            <b>{({rows: "Rating rows", blue_counts: "BLUE ratings", groups: "Groups", criticality: "Criticality", service_clusters: "Service field"} as Record<string, string>)[key] ?? key}</b>
            <span>{value ? "Passed" : "Check failed"}</span>
          </div>
        ))}
      </div>
      <p className="settings-hint">Checks validate the active dataset, not a fixed row count. {qa.status.baseline_matches ? "Current totals match the bundled reporting baseline." : "Totals differ from the reporting baseline; this is expected after a valid data update."} Missing optional fields are disclosed below, not silently filled.</p>
      <section className="table-panel"><h3>Missing values by column</h3><div className="table-scroll"><table className="score-table qa-table"><thead><tr><th>Column</th><th>Missing rows</th><th>Share of ratings</th></tr></thead><tbody>
        {qa.missing_values.filter((row: any) => row.missing > 0).map((row: any) => <tr key={row.column}><td>{row.column}</td><td>{row.missing.toLocaleString()}</td><td>{pct(row.missing / qa.status.rows * 100)}</td></tr>)}
      </tbody></table></div></section>
    </>
  );
}

function SettingsPage({ darkMode, setDarkMode, onDataSourceChange }: { darkMode: boolean; setDarkMode: (value: boolean) => void; onDataSourceChange: () => void }) {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [messageTone, setMessageTone] = useState<"ok" | "warn">("ok");
  useEffect(() => {
    getJson<AppSettings>("/api/app-settings")
      .then((payload) => {
        setSettings(payload);
      })
      .catch((err) => {
        setMessageTone("warn");
        setMessage(err.message);
      });
  }, []);
  async function handleCsvSelection(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setSaving(true);
    setMessage(null);
    try {
      const payload = await uploadFile<AppSettings>("/api/app-settings/csv-source/upload", file);
      setSettings(payload);
      onDataSourceChange();
      setMessageTone("ok");
      setMessage(`${file.name} is now the active dashboard source. The dashboard has refreshed, and the validated copy will remain active after restart.`);
    } catch (err) {
      setMessageTone("warn");
      setMessage(err instanceof Error ? err.message : "Unable to import CSV source.");
    } finally {
      setSaving(false);
    }
  }
  async function resetCsvSource() {
    setSaving(true);
    setMessage(null);
    try {
      const payload = await postJson<AppSettings>("/api/app-settings/csv-source", { path: null });
      setSettings(payload);
      onDataSourceChange();
      setMessageTone("ok");
      setMessage("The dashboard is using its default bundled/repository CSV again.");
    } catch (err) {
      setMessageTone("warn");
      setMessage(err instanceof Error ? err.message : "Unable to reset CSV source.");
    } finally {
      setSaving(false);
    }
  }
  return (
    <>
      <section className="page-intro">
        <span className="eyebrow">Settings</span>
        <h2>App Preferences</h2>
        <p>These settings affect the app shell and viewing behavior, not the dashboard data filters.</p>
      </section>
      <section className="settings-grid">
        <div className="settings-card">
          <div>
            <h3>Dark Mode</h3>
            <p>Switch the dashboard shell, tables, and controls to a darker viewing mode.</p>
          </div>
          <label className="switch">
            <input type="checkbox" checked={darkMode} onChange={(event) => setDarkMode(event.target.checked)} />
            <span></span>
          </label>
        </div>
        <div className="settings-card source-card">
          <div className="settings-copy">
            <h3>CSV Source</h3>
            <p>Export the updated master sheet as a UTF-8 CSV, then choose it here. Scores, groups, demographics and attention queues recalculate from the imported data.</p>
            <div className="settings-warning">
              <AlertTriangle size={18} />
              <span>Use the complete row-level master, not a pivot or score-summary export. Required fields and rating values are validated; an invalid import leaves the current source unchanged.</span>
            </div>
          </div>
          <div className="source-controls">
            <div className="source-paths">
              <span><b>Active source:</b> {settings ? (settings.source_is_managed_copy ? "Your imported master CSV · saved on this Mac" : "Default / configured master CSV") : "Loading…"}</span>
              <details><summary>Source file locations</summary><p>{settings?.csv_source_path}</p><p>Bundled default: {settings?.default_csv_source_path}</p></details>
            </div>
            <div className="source-actions">
              <label className="small-button file-picker-button">
                <FileUp size={16} />
                {saving ? "Importing..." : "Choose CSV"}
                <input type="file" accept=".csv,text/csv" disabled={saving} onChange={handleCsvSelection} />
              </label>
              <button className="small-button secondary" disabled={saving || !settings} onClick={resetCsvSource}>Reset default</button>
            </div>
            <p className="settings-hint">Saved imports survive closing, restarting and moving the app. This is a CSV snapshot, not a live connection to Excel or Google Sheets: upload a new export after each sheet update. Other open dashboard tabs refresh automatically.</p>
            <p className="settings-hint">All standard views calculate their scores from the active CSV. The bundled demo contains fictional data only.</p>
            {message ? <p role={messageTone === "warn" ? "alert" : "status"} className={`settings-message ${messageTone}`}>{message}</p> : null}
          </div>
        </div>
      </section>
    </>
  );
}

class AppErrorBoundary extends React.Component<{children: React.ReactNode}, {failed: boolean}> {
  state = {failed: false};
  static getDerivedStateFromError() { return {failed: true}; }
  render() {
    if (this.state.failed) return <main><section className="page-card"><h2>The dashboard needs a refresh</h2><p>A view could not load. Your saved CSV has not been changed.</p><button className="small-button" onClick={() => location.reload()}>Reload dashboard</button></section></main>;
    return this.props.children;
  }
}

startBrowserSession();
ReactDOM.createRoot(document.getElementById("root")!).render(<AppErrorBoundary><Shell /></AppErrorBoundary>);

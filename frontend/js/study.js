/* Study plan workspace: plans, results, what-if lab, user-entered quotes, checklist, scholarships, comparison. */
import { get, post, put, del, state } from "./api.js";
import { h } from "./cards.js";
import { tr, serverMsg } from "./i18n.js";
import { COUNTRY_NAMES } from "./geo.js";
import { CCY, dialog, confirmBox, field, input, select, setBusy, errBox, toast, skeleton } from "./ui.js";

let H = { askAssistant() {}, showRoute() {} };
export const setStudyHooks = (x) => (H = { ...H, ...x });

const n = (s) => Number(s);
const money = (v, c) => `${Number(v).toLocaleString(state.lang === "bn" ? "bn-BD" : "en-US", { minimumFractionDigits: c === "JPY" ? 0 : 2, maximumFractionDigits: c === "JPY" ? 0 : 2 })} ${c}`;
const stat = (v, l, cls = "") => h("div", { class: "stat " + cls }, h("b", {}, v), h("span", {}, l));
const section = (title, ...k) => h("section", { class: "dcard" }, h("h2", {}, title), ...k);
const bar = (pct, cls = "") => h("div", { class: "bar big " + cls, role: "progressbar", "aria-valuenow": Math.round(pct), "aria-valuemin": 0, "aria-valuemax": 100 }, h("i", { style: `width:${Math.max(0, Math.min(100, pct))}%` }));
const failView = (e, retry) => h("div", { class: "err" }, serverMsg(e.message), " ", h("button", { class: "link", type: "button", onclick: retry }, tr("retry")));
const fmtDate = (iso) => { try { return new Date(iso + "T00:00:00").toLocaleDateString(state.lang === "bn" ? "bn-BD" : "en-GB", { day: "numeric", month: "short", year: "numeric" }); } catch (_) { return iso; } };

let picked = new Set();

/* ---------------------------------------------------------------- list */
export async function renderStudy(root) {
  root.replaceChildren(skeleton(4));
  let d;
  try { d = await get("/api/study-plans"); } catch (e) { root.replaceChildren(failView(e, () => renderStudy(root))); return; }
  picked = new Set([...picked].filter((id) => d.items.some((p) => p.id === id)));
  const again = () => renderStudy(root);
  const cmpBtn = h("button", { class: "ghost", type: "button", disabled: true, onclick: () => openCompare(root, [...picked]) }, tr("sp_compare"));
  const upd = () => { cmpBtn.disabled = picked.size < 2 || picked.size > 3; };
  const cards = d.items.map((p) => {
    const r = p.result, c = p.currency;
    const chk = input({ type: "checkbox", "aria-label": tr("sp_compare") + ": " + p.name, ...(picked.has(p.id) ? { checked: true } : {}) });
    chk.checked = picked.has(p.id);
    chk.onchange = () => { chk.checked ? picked.add(p.id) : picked.delete(p.id); upd(); };
    return h("div", { class: "dcard plan" }, h("div", { class: "row2" }, h("label", { class: "chk" }, chk, h("b", {}, p.name)),
        h("span", { class: "sub" }, [p.uni_name || p.university_other, p.destination_country].filter(Boolean).join(" · "))),
      h("div", { class: "stats" }, stat(money(r.total_cost, c), tr("r_total")), stat(money(r.confirmed_gap, c), tr("r_gap")), stat(`${n(r.coverage_confirmed_pct).toFixed(0)}%`, tr("r_cov"))),
      bar(n(r.coverage_confirmed_pct)),
      h("div", { class: "row2" }, h("button", { class: "go mini", type: "button", onclick: () => openPlan(root, p.id) }, tr("sp_open")),
        h("span", {}, h("button", { class: "mini", type: "button", onclick: () => planForm(p, again) }, tr("edit")),
          h("button", { class: "mini", type: "button", onclick: async () => { try { await post(`/api/study-plans/${p.id}/duplicate`); again(); } catch (e) { toast(serverMsg(e.message), "err"); } } }, tr("sp_dup")),
          h("a", { class: "mini linkbtn", href: `/api/study-plans/${p.id}/report.pdf`, download: "" }, tr("sp_pdf")),
          h("button", { class: "mini danger", type: "button", onclick: async () => { if (!await confirmBox(tr("confirm_delete", { name: p.name }))) return;
            try { await del(`/api/study-plans/${p.id}`); toast(tr("deleted_ok")); again(); } catch (e) { toast(serverMsg(e.message), "err"); } } }, tr("delete")))));
  });
  root.replaceChildren(
    h("p", { class: "sub" }, tr("sp_intro")),
    h("div", { class: "row2" }, h("button", { class: "go", type: "button", onclick: () => planForm(null, again) }, "+ " + tr("sp_new")),
      h("button", { class: "ghost", type: "button", onclick: scholarshipDialog }, tr("scholarships")), cmpBtn),
    ...(cards.length ? cards : [h("div", { class: "empty" }, h("p", {}, tr("sp_empty")))]),
    h("p", { class: "sub disc" }, tr("disclaimer")));
  upd();
}

/* ---------------------------------------------------------------- create / edit */
function planForm(p, done) {
  const prof = state.auth?.profile || {};
  const f = {
    name: input({ type: "text", maxlength: 80, value: p?.name || "" }), dest: input({ type: "text", list: "countryList2", maxlength: 80, value: p?.destination_country || prof.study_country || "" }),
    uni: input({ type: "text", list: "uniList", maxlength: 100, value: p ? (p.uni_name || p.university_other || "") : (prof.uni_name || prof.university_other || "") }),
    program: input({ type: "text", maxlength: 100, value: p?.program || prof.program || "" }), ccy: select(CCY.map((c) => [c, c]), p?.currency || "USD"),
    years: input({ type: "number", min: 0.25, max: 10, step: "any", inputmode: "decimal", value: p?.duration_years ?? "" }),
    tuition: input({ type: "number", min: 0, step: "any", inputmode: "decimal", value: p?.annual_tuition ?? "" }), living: input({ type: "number", min: 0, step: "any", inputmode: "decimal", value: p?.monthly_living ?? "" }),
    one: input({ type: "number", min: 0, step: "any", inputmode: "decimal", value: p?.one_time_costs ?? 0 }), conf: input({ type: "number", min: 0, step: "any", inputmode: "decimal", value: p?.confirmed_funding ?? 0 }),
    pot: input({ type: "number", min: 0, step: "any", inputmode: "decimal", value: p?.potential_funding ?? 0 }), sav: input({ type: "number", min: 0, step: "any", inputmode: "decimal", value: p?.current_savings ?? 0 }),
    cap: input({ type: "number", min: 0, step: "any", inputmode: "decimal", value: p?.monthly_savings ?? 0 }), date: input({ type: "date", value: p?.target_date || prof.tuition_date || "" }),
    tg: input({ type: "number", min: -50, max: 100, step: "any", value: p?.tuition_growth_pct ?? 0 }), lg: input({ type: "number", min: -50, max: 100, step: "any", value: p?.living_growth_pct ?? 0 }),
  };
  const list = h("datalist", { id: "uniList" }), cl = h("datalist", { id: "countryList2" }, ...COUNTRY_NAMES.map((n) => h("option", { value: n }))); let unis = [];
  f.uni.addEventListener("input", async () => { if (f.uni.value.length < 2) return; try { const r = await get(`/api/universities?${new URLSearchParams({ q: f.uni.value, limit: 8 })}`); unis = r.items; list.replaceChildren(...unis.map((u) => h("option", { value: u.name }))); } catch (_) {} });
  const fail = errBox();
  dialog({ title: p ? tr("edit") : tr("sp_new"), wide: true, content: h("div", {}, list, cl, field(tr("name"), f.name),
      h("div", { class: "grid2" }, field(tr("sp_dest"), f.dest), field(tr("sp_uni"), f.uni)), h("div", { class: "grid3" }, field(tr("program"), f.program), field(tr("currency"), f.ccy), field(tr("sp_years"), f.years)),
      h("div", { class: "grid2" }, field(tr("sp_tuition"), f.tuition), field(tr("sp_living"), f.living)), field(tr("sp_onetime"), f.one),
      h("div", { class: "grid2" }, field(tr("sp_confirmed"), f.conf), field(tr("sp_potential"), f.pot)), h("p", { class: "sub" }, tr("r_potential_note")),
      h("div", { class: "grid3" }, field(tr("sp_savings"), f.sav), field(tr("sp_capacity"), f.cap), field(tr("sp_target"), f.date)),
      h("div", { class: "grid2" }, field(tr("sp_tg"), f.tg), field(tr("sp_lg"), f.lg)), fail),
    actions: [{ label: tr("cancel") }, { label: tr("save"), cls: "go", onClick: async (dlg) => {
      fail.textContent = "";
      const match = unis.find((u) => u.name === f.uni.value);
      const body = { name: f.name.value, currency: f.ccy.value, destination_country: f.dest.value || null, program: f.program.value || null,
        university_id: match ? match.id : null, university_other: match ? null : (f.uni.value || null),
        duration_years: f.years.value, annual_tuition: f.tuition.value, monthly_living: f.living.value, one_time_costs: f.one.value || 0,
        confirmed_funding: f.conf.value || 0, potential_funding: f.pot.value || 0, current_savings: f.sav.value || 0, monthly_savings: f.cap.value || 0,
        tuition_growth_pct: f.tg.value || 0, living_growth_pct: f.lg.value || 0, target_date: f.date.value || null };
      try { await (p ? put(`/api/study-plans/${p.id}`, body) : post("/api/study-plans", body)); toast(tr("saved_ok")); dlg.close(); done(); }
      catch (e) { fail.textContent = serverMsg(e.message); } } }] });
}

/* ---------------------------------------------------------------- detail */
async function openPlan(root, id) {
  root.replaceChildren(skeleton(5));
  let p;
  try { p = await get(`/api/study-plans/${id}`); } catch (e) { root.replaceChildren(failView(e, () => openPlan(root, id))); return; }
  const r = p.result, c = p.currency, total = n(r.total_cost) || 1;
  const seg = (v, cls, label) => h("i", { class: "seg " + cls, style: `width:${(n(v) / total) * 100}%`, title: `${label}: ${money(v, c)}` });
  const again = () => openPlan(root, id);
  const wiOut = h("div", { class: "wiout", "aria-live": "polite" });
  const wi = { t: input({ type: "number", step: "any", value: 0 }), l: input({ type: "number", step: "any", value: 0 }), x: input({ type: "number", min: 0, step: "any", value: 0 }) };
  const runWi = async () => {
    try {
      const w = await post(`/api/study-plans/${id}/whatif`, { tuition_change_pct: wi.t.value || 0, living_change_pct: wi.l.value || 0, extra_confirmed: wi.x.value || 0 });
      const ch = n(w.confirmed_gap_change);
      wiOut.replaceChildren(h("div", { class: "stats" }, stat(money(w.scenario.total_cost, c), tr("r_total")), stat(money(w.scenario.confirmed_gap, c), tr("r_gap")),
        stat((ch > 0 ? "+" : "") + money(ch, c), tr("wi_change"), ch > 0 ? "bad" : "good")), h("div", { class: "sub" }, tr("wi_note")));
    } catch (e) { wiOut.replaceChildren(h("div", { class: "err" }, serverMsg(e.message))); }
  };
  const quotesBox = h("div", {}), checkBox = h("div", {});
  root.replaceChildren(
    h("div", { class: "row2" }, h("button", { class: "mini", type: "button", onclick: () => renderStudy(root) }, "← " + tr("back")), h("h2", { class: "ptitle" }, p.name)),
    h("div", { class: "sub" }, [p.uni_name || p.university_other, p.program, p.destination_country].filter(Boolean).join(" · ")),
    section(tr("r_total"), h("div", { class: "stats" }, stat(money(r.total_cost, c), tr("r_total")), stat(money(r.confirmed_money, c), tr("r_confirmed")), stat(money(r.confirmed_gap, c), tr("r_gap"), n(r.confirmed_gap) > 0 ? "bad" : "good"),
        stat(money(r.potential_gap, c), tr("r_pgap")), stat(money(r.monthly_required, c), `${tr("r_monthly")} (${r.months_to_target} ${tr("r_months")})`)),
      h("div", { class: "stackbar", role: "img", "aria-label": `${tr("r_tuition")} ${money(r.tuition_total, c)}, ${tr("r_living")} ${money(r.living_total, c)}, ${tr("r_other")} ${money(r.one_time_total, c)}` },
        seg(r.tuition_total, "s1", tr("r_tuition")), seg(r.living_total, "s2", tr("r_living")), seg(r.one_time_total, "s3", tr("r_other"))),
      h("div", { class: "legend" }, h("span", {}, `■ ${tr("r_tuition")} ${money(r.tuition_total, c)}`), h("span", {}, `■ ${tr("r_living")} ${money(r.living_total, c)}`), h("span", {}, `■ ${tr("r_other")} ${money(r.one_time_total, c)}`)),
      h("div", { class: "sub" }, `${tr("r_cov")}: ${r.coverage_confirmed_pct}%`), bar(n(r.coverage_confirmed_pct)),
      h("div", { class: "sub" }, `+ ${tr("sp_potential")}: ${r.coverage_with_potential_pct}%`), bar(n(r.coverage_with_potential_pct), "pot"),
      h("p", { class: "sub" }, tr("r_potential_note")),
      h("div", { class: "row2" }, h("a", { class: "mini linkbtn", href: `/api/study-plans/${id}/report.pdf`, download: "" }, tr("sp_pdf")),
        h("button", { class: "mini", type: "button", onclick: () => H.askAssistant("Explain my study plan") }, tr("sp_explain")))),
    section(tr("fx_sens"), h("div", { class: "tablewrap" }, h("table", {}, h("tbody", {}, p.sensitivity.map((s) => h("tr", {}, h("td", {}, `${s.change_pct > 0 ? "+" : ""}${s.change_pct}%`), h("td", { class: "num" }, money(s.adjusted_total, c)))))))),
    section(tr("whatif"), h("div", { class: "grid3" }, field(tr("wi_t"), wi.t), field(tr("wi_l"), wi.l), field(tr("wi_x"), wi.x)), h("button", { class: "go mini", type: "button", onclick: runWi }, tr("wi_run")), wiOut),
    section(tr("quotes"), h("p", { class: "sub" }, tr("q_note")), quotesBox),
    section(tr("checklist"), checkBox),
    h("p", { class: "sub disc" }, tr("disclaimer")));
  H.showRoute?.(state.auth?.profile?.home_country, p.destination_country);
  loadQuotes(quotesBox, id, c); loadChecks(checkBox, id);
}

const pad2 = (x) => String(x).padStart(2, "0");
const nowLocal = () => { const d = new Date(); return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`; };
// seen_at comes from the server in UTC; show it in the browser's own time zone.
const fmtStamp = (s) => { try { const d = new Date(s + "Z"); return isNaN(d) ? s : d.toLocaleString(state.lang === "bn" ? "bn-BD" : "en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); } catch (_) { return s; } };
function vsMarket(i) {
  const v = n(i.vs_market_pct), m = i.market;
  const ref = `${tr("q_market")} ${m.rate} (${m.source === "live" ? tr("q_live") : tr("q_sample")})`;
  if (Math.abs(v) < 0.005) return `${tr("q_same_market")} · ${ref}`;
  return `${Math.abs(v).toFixed(2)}% ${v < 0 ? tr("q_below") : tr("q_above")} · ${ref}`;
}

async function loadQuotes(box, pid, planCcy) {
  let d;
  try { d = await get(`/api/study-plans/${pid}/quotes`); } catch (e) { box.replaceChildren(failView(e, () => loadQuotes(box, pid, planCcy))); return; }
  const q = { prov: input({ type: "text", maxlength: 80 }), from: select(CCY.map((x) => [x, x]), state.auth?.profile?.currency || "BDT"), to: select(CCY.map((x) => [x, x]), planCcy),
    amt: input({ type: "number", min: 0, step: "any" }), rate: input({ type: "number", min: 0, step: "any" }), fee: input({ type: "number", min: 0, step: "any", value: 0 }), fixed: input({ type: "number", min: 0, step: "any", value: 0 }),
    conv: select([["added", tr("q_added")], ["included", tr("q_included")]], "added"),
    asof: input({ type: "datetime-local", value: nowLocal(), max: nowLocal() }) };
  const mk = h("div", { class: "note", "aria-live": "polite" });
  let mkSeq = 0;
  const loadMarket = async () => {
    const my = ++mkSeq;
    if (q.from.value === q.to.value) { mk.textContent = ""; return; }
    try {
      const m = await get(`/api/market-rate?${new URLSearchParams({ from: q.from.value, to: q.to.value })}`);
      if (my !== mkSeq) return;
      mk.replaceChildren(h("b", {}, `1 ${m.from} = ${m.rate} ${m.to}`), " · ", m.source === "live" ? `${tr("q_live")} ${m.updated || ""}` : tr("q_sample"), h("div", { class: "sub" }, m.label));
    } catch (_) { if (my === mkSeq) mk.textContent = ""; }
  };
  q.from.addEventListener("change", loadMarket); q.to.addEventListener("change", loadMarket); loadMarket();
  const fail = errBox();
  const add = h("button", { class: "go mini", type: "button", onclick: async () => {
    fail.textContent = "";
    try { await post(`/api/study-plans/${pid}/quotes`, { provider: q.prov.value, send_currency: q.from.value, receive_currency: q.to.value, amount: q.amt.value, rate: q.rate.value, fee_percent: q.fee.value || 0, fixed_fee: q.fixed.value || 0, convention: q.conv.value, as_of: q.asof.value ? new Date(q.asof.value).toISOString().slice(0, 16) : null }); loadQuotes(box, pid, planCcy); }
    catch (e) { fail.textContent = serverMsg(e.message); } } }, tr("q_add"));
  box.replaceChildren(
    ...d.items.map((i) => h("div", { class: "row2 cmp" }, h("span", {}, h("b", {}, i.provider), i.best ? h("span", { class: "badge" }, tr("q_best")) : null,
        h("div", { class: "sub" }, `${tr("q_paid")}: ${money(i.result.total_paid, i.send_currency)} · ${tr("q_gets")}: ${money(i.result.recipient_gets, i.receive_currency)} · ${i.source_label}`),
        h("div", { class: "sub" }, `${tr("q_asof")}: ${fmtStamp(i.seen_at)}${i.seen_is_entered ? "" : " (" + tr("q_saved_time") + ")"} · ${tr("q_rate_short")} ${i.rate}`,
          i.stale ? h("span", { class: "badge warn" }, tr("q_stale")) : null),
        h("div", { class: "sub" }, vsMarket(i))),
      h("button", { class: "mini danger", type: "button", "aria-label": tr("delete") + " " + i.provider, onclick: async () => { try { await del(`/api/study-quotes/${i.id}`); loadQuotes(box, pid, planCcy); } catch (e) { toast(serverMsg(e.message), "err"); } } }, tr("delete")))),
    h("div", { class: "grid3" }, field(tr("q_provider"), q.prov), field(tr("q_from"), q.from), field(tr("q_to"), q.to)),
    h("div", { class: "grid3" }, field(tr("q_amount"), q.amt), field(tr("q_rate"), q.rate), field(tr("q_conv"), q.conv)),
    h("div", { class: "grid2" }, field(tr("q_fee"), q.fee), field(tr("q_fixed"), q.fixed)), field(tr("q_when"), q.asof), mk, fail, add);
}

async function loadChecks(box, pid) {
  let d;
  try { d = await get(`/api/checklist?plan_id=${pid}`); } catch (e) { box.replaceChildren(failView(e, () => loadChecks(box, pid))); return; }
  const t = input({ type: "text", maxlength: 200, placeholder: tr("ck_ph"), "aria-label": tr("ck_ph") });
  const add = async () => { if (!t.value.trim()) return; try { await post("/api/checklist", { title: t.value, plan_id: pid }); loadChecks(box, pid); } catch (e) { toast(serverMsg(e.message), "err"); } };
  t.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); add(); } });
  box.replaceChildren(...d.items.map((i) => {
    const c = input({ type: "checkbox", id: "ck" + i.id }); c.checked = i.done;
    c.onchange = async () => { try { await put(`/api/checklist/${i.id}`, { done: c.checked }); } catch (e) { c.checked = !c.checked; toast(serverMsg(e.message), "err"); } };
    return h("div", { class: "row2 ck" }, h("span", { class: "chk" }, c, h("label", { for: "ck" + i.id }, i.title)),
      h("button", { class: "mini danger", type: "button", "aria-label": tr("delete") + " " + i.title, onclick: async () => { try { await del(`/api/checklist/${i.id}`); loadChecks(box, pid); } catch (e) { toast(serverMsg(e.message), "err"); } } }, "×"));
  }), h("div", { class: "row2" }, t, h("button", { class: "mini", type: "button", onclick: add }, tr("ck_add"))));
}

/* ---------------------------------------------------------------- compare & scholarships */
async function openCompare(root, ids) {
  root.replaceChildren(skeleton(4));
  let d;
  try { d = await get(`/api/study-plans/compare?ids=${ids.join(",")}`); } catch (e) { root.replaceChildren(failView(e, () => renderStudy(root))); return; }
  const rows = [["r_total", "total_cost"], ["r_confirmed", "confirmed_money"], ["r_gap", "confirmed_gap"], ["r_pgap", "potential_gap"], ["r_monthly", "monthly_required"], ["r_cov", "coverage_confirmed_pct"]];
  root.replaceChildren(h("div", { class: "row2" }, h("button", { class: "mini", type: "button", onclick: () => renderStudy(root) }, "← " + tr("back")), h("h2", { class: "ptitle" }, tr("compare_title"))),
    h("div", { class: "tablewrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, ""), d.items.map((p) => h("th", { class: "num" }, p.name, h("div", { class: "sub" }, p.currency))))),
      h("tbody", {}, rows.map(([lab, k]) => h("tr", {}, h("td", {}, tr(lab)), d.items.map((p) => h("td", { class: "num" }, k === "coverage_confirmed_pct" ? p.result[k] + "%" : money(p.result[k], p.currency)))))))),
    h("p", { class: "sub" }, tr("compare_cur")));
}

async function scholarshipDialog() {
  const body = h("div", {}, skeleton(3));
  dialog({ title: tr("scholarships"), wide: true, content: body, actions: [{ label: tr("close"), cls: "go" }] });
  try {
    const d = await get("/api/scholarships");
    body.replaceChildren(h("p", { class: "sub" }, tr("sch_note")), ...d.items.map((s) => h("div", { class: "row2 cmp" }, h("span", {}, h("b", {}, s.name), h("div", { class: "sub" }, `${s.provider} · ${s.destination}${s.level ? " · " + s.level : ""}`)),
      s.url ? h("a", { class: "mini linkbtn", href: s.url, target: "_blank", rel: "noopener noreferrer" }, tr("sch_open")) : null)));
  } catch (e) { body.replaceChildren(h("div", { class: "err" }, serverMsg(e.message))); }
}

/* Home dashboard and "My plans" (budgets, tuition plans, saved comparisons). */
import { get, post, put, del, state, ApiError } from "./api.js";
import { h, money } from "./cards.js";
import { tr, serverMsg } from "./i18n.js";
import { CCY, dialog, confirmBox, field, input, select, setBusy, errBox, toast, skeleton } from "./ui.js";

let H = { askAssistant() {}, openProfile() {}, openWallet() {}, showTab() {}, prefill() {}, setRoute() {} };
export const setDashHooks = (x) => (H = { ...H, ...x });

const bar = (pct, cls = "") => h("div", { class: "bar big " + cls, role: "progressbar", "aria-valuenow": Math.round(pct), "aria-valuemin": 0, "aria-valuemax": 100 }, h("i", { style: `width:${Math.max(0, Math.min(100, pct))}%` }));
const stat = (v, l) => h("div", { class: "stat" }, h("b", {}, v), h("span", {}, l));
const empty = (msg, btn) => h("div", { class: "empty" }, h("p", {}, msg), btn || null);
const section = (title, ...kids) => h("section", { class: "dcard" }, h("h2", {}, title), ...kids);
const failView = (e, retry) => h("div", { class: "err" }, serverMsg(e.message || tr("load_err")), " ", h("button", { class: "link", type: "button", onclick: retry }, tr("retry")));
const fmtDate = (iso) => { try { return new Date(iso + "T00:00:00").toLocaleDateString(state.lang === "bn" ? "bn-BD" : "en-GB", { day: "numeric", month: "short", year: "numeric" }); } catch (_) { return iso; } };

/* ------------------------------------------------------------------ dashboard */
export async function renderHome(root) {
  root.replaceChildren(skeleton(5));
  let d;
  try { d = await get("/api/dashboard"); } catch (e) { root.replaceChildren(failView(e, () => renderHome(root))); return; }
  const p = d.profile, ccy = p.currency;
  const uni = p.uni_name || p.university_other;
  const cards = [];

  cards.push(h("div", { class: "welcome" }, h("h2", {}, tr("welcome_back", { name: d.name.split(" ")[0] })),
    h("button", { class: "mini", type: "button", onclick: H.openProfile }, tr("profile"))));

  if (d.notifications.length) cards.push(section(tr("reminders"), ...d.notifications.map((n) => h("div", { class: "rem" }, h("span", {}, "🔔 " + serverMsg(n.message)),
      h("button", { class: "mini", type: "button", onclick: async (e) => { try { await post(`/api/notifications/${n.id}/read`); e.target.closest(".rem").remove(); } catch (er) { toast(serverMsg(er.message), "err"); } } }, tr("dismiss")))),
    h("p", { class: "sub" }, tr("rem_note"))));

  cards.push(section(tr("uni_card"), uni ? h("div", {}, h("b", {}, uni), p.uni_name ? h("div", { class: "sub" }, `${p.uni_city ? p.uni_city + ", " : ""}${p.uni_country}`) : null,
      p.program ? h("div", { class: "sub" }, `${p.program}${p.study_level ? " · " + p.study_level : ""}`) : null) : empty(tr("no_uni"), h("button", { class: "mini", type: "button", onclick: H.openProfile }, tr("profile"))),
    h("p", { class: "sub" }, tr("uni_note"))));

  const b = d.budget;
  cards.push(section(tr("budget_card"), b ? h("div", {}, h("div", { class: "sub" }, b.name),
      h("div", { class: "stats" }, stat(money(b.result.income, b.currency), tr("income")), stat(money(b.result.total_expenses, b.currency), tr("expenses")),
        stat(money(b.result.surplus, b.currency), tr("left_over")), stat(`${b.result.savings_rate.toFixed(0)}%`, `${tr("savings_rate")} (${b.target_pct}%)`))) : empty(tr("no_budget"))));

  cards.push(section(tr("savings_card"), d.tuition.length ? d.tuition.slice(0, 3).map((t) => h("div", { class: "tp" }, h("div", { class: "row2" }, h("b", {}, t.name), h("span", {}, `${t.progress_pct.toFixed(0)}%`)),
      bar(t.progress_pct), h("div", { class: "sub" }, `${money(t.saved, t.home_currency)} / ${money(t.total_home, t.home_currency)}`))) : empty(tr("no_tuition"))));

  cards.push(section(tr("deadlines"), d.upcoming.length ? d.upcoming.map((t) => h("div", { class: "row2 dl" }, h("span", {}, h("b", {}, fmtDate(t.next_due)), ` · ${t.name}`),
      h("span", { class: t.days_to_next_due <= 14 ? "pill-warn" : "sub" }, `${t.days_to_next_due} d`))) : empty(tr("no_deadlines"))));

  cards.push(section(tr("saved_cmp"), d.comparisons.length ? d.comparisons.map((c) => cmpRow(c, () => renderHome(root))) : empty(tr("no_cmp"))));

  cards.push(section(tr("activity"), d.records.length ? d.records.map((r) => h("div", { class: "row2 act" }, h("span", {}, h("code", {}, r.ref), ` ${r.kind}`),
      h("span", { class: "sub" }, r.send !== undefined ? money(r.send, r.send_currency) : r.amount !== undefined ? money(r.amount, r.currency) : ""))) : empty(tr("no_activity"))));

  cards.push(section(tr("quick"), h("div", { class: "qa" }, [
    [tr("qa_compare"), () => H.showTab("explore")], [tr("qa_budget"), () => H.showTab("plans")], [tr("qa_tuition"), () => H.showTab("plans")],
    [tr("qa_invoice"), () => invoiceDialog()], [tr("qa_ask"), () => H.showTab("chat")], [tr("wallet"), H.openWallet]].map(([l, f]) => h("button", { class: "ghost", type: "button", onclick: f }, l)))));

  cards.push(h("p", { class: "sub disc" }, d.disclaimer));
  root.replaceChildren(...cards);
}

function cmpRow(c, refresh) {
  return h("div", { class: "row2 cmp" }, h("span", {}, h("b", {}, c.label), h("div", { class: "sub" }, `${c.from_ccy}→${c.to_ccy} · ${c.purpose} · ${tr("best")}: ${c.best.split(" (")[0]}`)),
    h("span", {}, h("button", { class: "mini", type: "button", onclick: () => { H.setRoute(c.from_ccy, c.to_ccy); H.askAssistant(`Compare the cheapest way to pay ${Math.round(c.amount)} ${c.to_ccy} ${c.purpose} from ${c.from_ccy}`); } }, tr("open_chat")),
      h("button", { class: "mini danger", type: "button", "aria-label": tr("delete") + " " + c.label, onclick: async () => {
        if (!await confirmBox(tr("confirm_delete", { name: c.label }))) return;
        try { await del(`/api/comparisons/${c.id}`); toast(tr("deleted_ok")); refresh(); } catch (e) { toast(serverMsg(e.message), "err"); } } }, tr("delete"))));
}

/* ------------------------------------------------------------------ invoice upload */
function invoiceDialog() {
  const file = input({ type: "file", accept: "application/pdf,.pdf" }); const fail = errBox();
  const dlg = dialog({ title: tr("qa_invoice"), content: h("div", {}, h("p", { class: "sub" }, tr("inv_note")), field(tr("inv_upload"), file), fail),
    actions: [{ label: tr("cancel") }, { label: tr("send_to_checker"), cls: "go", onClick: async () => {
      fail.textContent = ""; const f = file.files[0];
      if (!f) { fail.textContent = tr("inv_upload"); return; }
      if (f.size > 2 * 1024 * 1024) { fail.textContent = "File too large (limit 2 MB)."; return; }
      try {
        const b64 = await new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(",")[1]); r.onerror = no; r.readAsDataURL(f); });
        const r = await post(`/api/invoice/extract${state.sessionId ? "?session_id=" + state.sessionId : ""}`, { filename: f.name, content_b64: b64 });
        dlg.close(); H.showTab("chat"); H.askAssistant("Check this invoice: " + r.text);
      } catch (e) { fail.textContent = serverMsg(e.message); } } }] });
}

/* ------------------------------------------------------------------ My plans */
export async function renderPlans(root) {
  root.replaceChildren(skeleton(5));
  let b, t, c;
  try { [b, t, c] = await Promise.all([get("/api/budgets"), get("/api/tuition-plans"), get("/api/comparisons")]); }
  catch (e) { root.replaceChildren(failView(e, () => renderPlans(root))); return; }
  const again = () => renderPlans(root);
  const del_ = (url, name) => async () => { if (!await confirmBox(tr("confirm_delete", { name }))) return; try { await del(url); toast(tr("deleted_ok")); again(); } catch (e) { toast(serverMsg(e.message), "err"); } };

  root.replaceChildren(
    section(tr("budgets"), h("button", { class: "go mini", type: "button", onclick: () => budgetForm(null, again) }, "+ " + tr("new_budget")),
      b.items.length ? b.items.map((x) => h("div", { class: "plan" }, h("div", { class: "row2" }, h("b", {}, x.name), h("span", {}, h("button", { class: "mini", type: "button", onclick: () => budgetForm(x, again) }, tr("edit")),
          h("button", { class: "mini danger", type: "button", onclick: del_(`/api/budgets/${x.id}`, x.name) }, tr("delete")))),
        h("div", { class: "stats" }, stat(money(x.result.income, x.currency), tr("income")), stat(money(x.result.total_expenses, x.currency), tr("expenses")), stat(money(x.result.surplus, x.currency), tr("left_over")),
          stat(`${x.result.savings_rate.toFixed(0)}%`, `${tr("savings_rate")} (${x.target_pct}%)`)),
        ...x.result.alerts.map((a) => h("div", { class: "note warn" }, a)))) : empty(tr("no_budget"))),
    section(tr("tuition_plans"), h("button", { class: "go mini", type: "button", onclick: () => tuitionForm(null, again) }, "+ " + tr("new_tuition")),
      t.items.length ? t.items.map((x) => h("div", { class: "plan" }, h("div", { class: "row2" }, h("b", {}, x.name), h("span", {}, h("button", { class: "mini", type: "button", onclick: () => tuitionForm(x, again) }, tr("edit")),
          h("button", { class: "mini danger", type: "button", onclick: del_(`/api/tuition-plans/${x.id}`, x.name) }, tr("delete")))),
        h("div", { class: "sub" }, `${money(x.total, x.currency)} · ${x.status === "upcoming" ? `${tr("next_due")}: ${fmtDate(x.next_due)} (${x.days_to_next_due} d)` : tr("past_dues")}`),
        h("div", { class: "sub" }, tr("progress")), bar(x.progress_pct),
        x.plan ? h("div", { class: "stats" }, stat(money(x.plan.required_monthly, x.home_currency), tr("monthly_need")),
          stat(x.plan.feasible === null ? "n/a" : x.plan.feasible ? tr("on_track") : money(x.plan.gap, x.home_currency), tr("shortfall"))) : null,
        h("div", { class: "sub" }, x.note))) : empty(tr("no_tuition"))),
    section(tr("saved_cmp"), c.items.length ? c.items.map((x) => cmpRow(x, again)) : empty(tr("no_cmp"))),
    h("p", { class: "sub disc" }, tr("disclaimer")));
}

function budgetForm(b, done) {
  const name = input({ type: "text", maxlength: 60, value: b?.name || "" }), income = input({ type: "number", min: 0, step: "any", inputmode: "decimal", value: b?.income ?? "" });
  const ccy = select(CCY.map((x) => [x, x]), b?.currency || state.auth?.profile?.currency || "BDT"), target = input({ type: "number", min: 0, max: 90, step: "any", value: b?.target_pct ?? 20 });
  const rows = h("div", { class: "exp" }); const fail = errBox();
  const addRow = (k = "", v = "") => { const r = h("div", { class: "exprow" }, input({ type: "text", maxlength: 40, placeholder: tr("category"), "aria-label": tr("category"), value: k }),
    input({ type: "number", min: 0, step: "any", inputmode: "decimal", placeholder: tr("amount"), "aria-label": tr("amount"), value: v }),
    h("button", { class: "mini danger", type: "button", "aria-label": tr("delete"), onclick: () => r.remove() }, "×")); rows.append(r); };
  Object.entries(b?.expenses || { rent: "", food: "", transport: "" }).forEach(([k, v]) => addRow(k, v));
  const dlg = dialog({ title: b ? tr("edit") : tr("new_budget"), wide: true, content: h("div", {}, h("div", { class: "grid2" }, field(tr("name"), name), field(tr("currency"), ccy)),
      h("div", { class: "grid2" }, field(tr("income"), income), field(tr("target"), target)), h("h3", { class: "sect" }, tr("expenses")), rows,
      h("button", { class: "mini", type: "button", onclick: () => addRow() }, "+ " + tr("add_expense")), fail),
    actions: [{ label: tr("cancel") }, { label: tr("save"), cls: "go", onClick: async (d) => {
      fail.textContent = ""; const expenses = {};
      for (const r of rows.children) { const [k, v] = r.querySelectorAll("input"); if (k.value.trim() && v.value !== "") expenses[k.value.trim()] = Number(v.value); }
      try { const body = { name: name.value, income: Number(income.value), currency: ccy.value, expenses, target_pct: Number(target.value) };
        await (b ? put(`/api/budgets/${b.id}`, body) : post("/api/budgets", body)); toast(tr("saved_ok")); d.close(); done(); }
      catch (e) { fail.textContent = serverMsg(e.message); } } }] });
}

function tuitionForm(x, done) {
  const name = input({ type: "text", maxlength: 60, value: x?.name || "" }), total = input({ type: "number", min: 0, step: "any", inputmode: "decimal", value: x?.total ?? "" });
  const ccy = select(CCY.map((c) => [c, c]), x?.currency || "USD"), home = select(CCY.map((c) => [c, c]), x?.home_currency || state.auth?.profile?.currency || "BDT");
  const dues = h("textarea", { rows: 3, "aria-label": tr("due_dates") }); dues.value = (x?.due_dates || []).join("\n");
  const saved = input({ type: "number", min: 0, step: "any", inputmode: "decimal", value: x?.saved ?? 0 }), monthly = input({ type: "number", min: 0, step: "any", inputmode: "decimal", value: x?.monthly_saving ?? "" });
  const fail = errBox();
  dialog({ title: x ? tr("edit") : tr("new_tuition"), wide: true, content: h("div", {}, field(tr("name"), name), h("div", { class: "grid3" }, field(tr("total"), total), field(tr("tcurrency"), ccy), field(tr("home_ccy"), home)),
      field(tr("due_dates"), dues), h("div", { class: "grid2" }, field(tr("saved_so_far"), saved), field(tr("monthly_cap"), monthly)), fail),
    actions: [{ label: tr("cancel") }, { label: tr("save"), cls: "go", onClick: async (d) => {
      fail.textContent = "";
      try { const body = { name: name.value, total: Number(total.value), currency: ccy.value, home_currency: home.value, due_dates: dues.value.split(/[\s,]+/).filter(Boolean), saved: Number(saved.value || 0), monthly_saving: monthly.value === "" ? null : Number(monthly.value) };
        await (x ? put(`/api/tuition-plans/${x.id}`, body) : post("/api/tuition-plans", body)); toast(tr("saved_ok")); d.close(); done(); }
      catch (e) { fail.textContent = serverMsg(e.message); } } }] });
}

/* "Save this comparison": used by route cards and the Cost Explorer. Guests are told to sign in. */
export async function saveComparison({ amount, from, to, purpose, basis = "receive" }) {
  if (!state.auth) { toast(tr("need_signin"), "err"); return; }
  try { await post("/api/comparisons", { amount, from_currency: from, to_currency: to, purpose, basis }); toast(tr("saved_ok")); } catch (e) { toast(serverMsg(e.message), "err"); }
}

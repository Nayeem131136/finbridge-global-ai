/* Card renderers. All text goes through textContent / text nodes, never innerHTML. */
import { tr } from "./i18n.js";
export function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}
const svgNS = "http://www.w3.org/2000/svg";
const nf = (n, d = 2) => Number(n).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
export const money = (n, c) => `${nf(n, ["BDT", "JPY", "INR"].includes(c) ? 0 : 2)} ${c}`;
const hours = (x) => (x < 24 ? `${x}h` : `${Math.round(x / 24)} day${x >= 48 ? "s" : ""}`);
const stat = (v, label) => h("div", { class: "stat" }, h("b", {}, v), h("span", {}, label));

export function countUp(el, to, fmt, ms = 900) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) { el.textContent = fmt(to); return; }
  const t0 = performance.now();
  const step = (t) => {
    const p = Math.min(1, (t - t0) / ms);
    el.textContent = fmt(to * (1 - Math.pow(1 - p, 3)));
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function annotated(d) {
  if (!d.text || !(d.highlights || []).length) return null;
  const parts = []; let last = 0;
  for (const hl of d.highlights) {
    if (hl.start > last) parts.push(d.text.slice(last, hl.start));
    parts.push(h("mark", { class: `hl ${hl.level}`, title: hl.label, tabindex: "0" }, d.text.slice(hl.start, hl.end), h("sup", {}, "!")));
    last = hl.end;
  }
  if (last < d.text.length) parts.push(d.text.slice(last));
  const labels = [...new Set(d.highlights.map((x) => x.label))];
  return h("div", { class: "annot" }, h("div", { class: "sub" }, "What the checker noticed in your text:"), h("p", { class: "doc" }, parts),
    h("div", { class: "legend" }, labels.map((l) => h("span", {}, l))));
}

export function makeCards({ onConfirm, onSave }) {
  return {
    fx_rate: (d) => {
      const big = h("div", { class: "big" }, "");
      countUp(big, d.converted, (v) => `${money(d.amount, d.from)} = ${money(v, d.to)}`);
      return h("div", { class: "card" }, h("h4", {}, "Exchange rate"), big,
        h("div", { class: "sub" }, `1 ${d.from} = ${d.rate.toFixed(4)} ${d.to} (${d.source_label || "illustrative sandbox rate"})`));
    },
    fx_timing: (d) => {
      const w = 300, ht = 64, min = Math.min(...d.series), max = Math.max(...d.series);
      const pts = d.series.map((v, i) => `${(i / (d.series.length - 1)) * w},${ht - 4 - ((v - min) / (max - min || 1)) * (ht - 8)}`).join(" ");
      const svg = document.createElementNS(svgNS, "svg");
      svg.setAttribute("viewBox", `0 0 ${w} ${ht}`); svg.setAttribute("class", "spark"); svg.setAttribute("preserveAspectRatio", "none");
      svg.setAttribute("role", "img"); svg.setAttribute("aria-label", `30-day ${d.from} to ${d.to} rate`);
      const line = document.createElementNS(svgNS, "polyline");
      line.setAttribute("points", pts); line.setAttribute("fill", "none"); line.setAttribute("stroke", "#2de2c5");
      line.setAttribute("stroke-width", "2"); line.setAttribute("vector-effect", "non-scaling-stroke");
      svg.append(line);
      const tone = { favorable: "good", unfavorable: "warn", neutral: "info" }[d.signal];
      return h("div", { class: "card" }, h("h4", {}, `${d.from} to ${d.to} timing, last 30 days`), svg,
        h("div", { class: "stats" }, stat(d.signal.toUpperCase(), "signal"), stat(`${d.percentile}`, "percentile (0 low, 100 high)"),
          stat(`${d.vs_avg_pct >= 0 ? "+" : ""}${d.vs_avg_pct.toFixed(2)}%`, "vs 30-day average")),
        h("div", { class: `note ${tone}` }, d.advice), h("div", { class: "sub" }, d.disclaimer));
    },
    route_comparison: (d) => {
      const rows = d.quotes.map((q, i) => h("tr", { class: i === 0 ? "best" : "" },
        h("td", {}, q.provider, i === 0 ? h("span", { class: "badge" }, "BEST") : null, h("div", { class: "sub" }, q.note)),
        h("td", { class: "num" }, money(q.send_amount, q.send_currency)),
        h("td", { class: "num" }, money(q.receive_amount, q.receive_currency)),
        h("td", { class: "num" }, `${q.total_cost_pct.toFixed(2)}%`, h("div", { class: "sub" }, money(q.total_cost, q.send_currency))),
        h("td", { class: "num" }, hours(q.speed_hours))));
      return h("div", { class: "card" }, h("h4", {}, `Route comparison (${d.purpose})`),
        h("div", { class: "tablewrap" }, h("table", {},
          h("thead", {}, h("tr", {}, h("th", {}, "Provider"), h("th", { class: "num" }, "You pay"), h("th", { class: "num" }, "They get"),
            h("th", { class: "num" }, "Total cost"), h("th", { class: "num" }, "Time"))), h("tbody", {}, rows))),
        d.quotes.length > 1 && d.savings_vs_worst > 0 ? h("div", { class: "note good" }, `Best option saves ${money(d.savings_vs_worst, d.quotes[0].send_currency)} compared with the most expensive route.`) : null,
        d.excluded.length ? h("div", { class: "sub" }, "Not available: " + d.excluded.map((e) => `${e.provider} (${e.reason})`).join(" ")) : null,
        h("div", { class: "sub" }, d.data_note),
        onSave ? h("div", { class: "cta" }, h("button", { type: "button", class: "mini", onclick: () => onSave({ amount: Math.round(d.quotes[0].receive_amount * 100) / 100, from: d.quotes[0].send_currency, to: d.quotes[0].receive_currency, purpose: d.purpose, basis: "receive" }) }, tr("save_cmp"))) : null);
    },
    budget: (d) => h("div", { class: "card" }, h("h4", {}, "Monthly budget"),
      h("div", { class: "stats" }, stat(money(d.income, d.currency), "income"), stat(money(d.total_expenses, d.currency), "expenses"),
        stat(money(d.surplus, d.currency), "left over"), stat(`${d.savings_rate.toFixed(0)}%`, `savings rate (goal ${d.target_pct}%)`)),
      d.lines.map((l) => h("div", { class: "line" }, h("span", {}, l.category),
        h("div", { class: "bar" }, h("i", { style: `width:${Math.min(100, l.share_pct)}%` })), h("span", {}, money(l.amount, d.currency)))),
      d.alerts.map((a) => h("div", { class: "note warn" }, a)), d.tips.map((a) => h("div", { class: "note" }, a))),
    tuition_plan: (d) => h("div", { class: "card" }, h("h4", {}, "Tuition plan"),
      h("div", { class: "stats" }, stat(money(d.total, d.currency), "total"), stat(money(d.required_monthly, d.home_currency), "save per month"),
        stat(d.feasible === null ? "n/a" : d.feasible ? "On track" : `Short ${money(d.gap, d.home_currency)}/mo`, "vs your capacity")),
      h("div", { class: "tl" }, d.schedule.map((s) => h("div", { class: "it" }, h("b", {}, s.due),
        h("div", {}, `${money(s.amount, s.currency)} (about ${money(s.amount_home, s.home_currency)})`,
          h("div", { class: "sub" }, `${s.days_left} days left. Reminders: ${s.remind_on.join(", ")}`))))),
      h("h4", { style: "margin-top:10px" }, "Convert in tranches"),
      h("div", { class: "tl" }, d.tranche_plan.map((t) => h("div", { class: "it" }, h("b", {}, t.when), h("div", {}, `Convert ${money(t.convert_home, d.home_currency)}`)))),
      h("div", { class: `note ${d.fx_signal === "favorable" ? "good" : d.fx_signal === "unfavorable" ? "warn" : ""}` }, d.fx_advice)),
    credit_roadmap: (d) => h("div", { class: "card" }, h("h4", {}, `Credit roadmap, ${d.horizon}`),
      h("ol", { class: "steps" }, d.steps.map((s) => h("li", {}, h("b", {}, s.step), h("div", { class: "sub" }, `${s.when}. ${s.why}`)))),
      h("h4", { style: "margin-top:12px" }, "Avoid"), d.avoid.map((a) => h("div", { class: "note warn" }, a)),
      h("div", { class: "sub" }, d.disclaimer)),
    invoice_check: (d) => h("div", { class: "card" }, h("h4", {}, "Invoice check"),
      h("div", { class: `verdict ${d.verdict}` }, { do_not_pay: "Do not pay yet", review: "Needs review", looks_consistent: "Looks consistent" }[d.verdict]),
      h("div", { class: "stats" }, stat(d.amount ? money(d.amount, d.currency) : "not found", "amount"), stat(d.due_date || "not found", "due date"),
        stat(d.beneficiary || "not found", d.verified_beneficiary ? "beneficiary (verified)" : "beneficiary"), stat(d.account_masked || "not found", "account")),
      annotated(d),
      d.flags.map((f) => h("div", { class: `note ${f.level}` }, f.msg)), h("div", { class: "sub" }, tr("inv_note"))),
    study_plan: (d) => h("div", { class: "card" }, h("h4", {}, `Study plan: ${d.name}`),
      h("div", { class: "stats" }, stat(money(Number(d.total_cost), d.currency), "total estimated cost"), stat(money(Number(d.confirmed_gap), d.currency), "confirmed gap"),
        stat(`${d.coverage_confirmed_pct}%`, "covered by confirmed money"), stat(money(Number(d.monthly_required), d.currency), `save per month (${d.months_to_target} months)`)),
      h("div", { class: "note" }, "Potential scholarships are not counted as confirmed funding. Server-calculated estimates, not advice.")),
    account: (d) => h("div", { class: "card" }, h("h4", {}, "Sandbox account"),
      h("div", { class: "stats" }, Object.entries(d.balances).map(([c, v]) => stat(money(v, c), c))),
      d.transactions.length ? d.transactions.map((t) => h("div", { class: "note" }, `${t.ref}: ${money(t.send, t.send_currency)} to ${t.beneficiary} (${t.status})`)) : h("div", { class: "sub" }, "No transfers yet.")),
    blocked: (d) => h("div", { class: "card" }, h("h4", {}, "Transfer blocked"), d.reasons.map((r) => h("div", { class: "note bad" }, r))),
    confirmation: (d) => h("div", { class: "card" }, h("h4", {}, "Transfer waiting for you"),
      h("div", {}, `${money(d.send, d.send_currency)} to ${d.beneficiary} (they receive ${money(d.receive, d.receive_currency)})`),
      d.warnings.map((w) => h("div", { class: "note warn" }, w)),
      h("div", { class: "cta" }, h("button", { type: "button", onclick: () => onConfirm(d) }, "Review and confirm"))),
  };
}

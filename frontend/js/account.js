/* Sign up / sign in / reset screens, profile editor, wallet dialogs. */
import { COUNTRY_NAMES } from "./geo.js";
import { api, get, post, put, del, state, signedIn } from "./api.js";
import { h, money } from "./cards.js";
import { tr, serverMsg, levelName, isBn } from "./i18n.js";
import { CCY, TIMEZONES, dialog, confirmBox, field, input, select, setBusy, errBox, toast, invalid } from "./ui.js";

let hooks = { onAuth() {}, onGuest() {}, onSignedOut() {}, onProfile() {} };
export const setAuthHooks = (x) => (hooks = { ...hooks, ...x });
const EMAIL = /^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$/;

/* ------------------------------------------------------------------ auth screens */
const screen = () => document.getElementById("authScreen");
export function hideAuth() { screen().hidden = true; screen().replaceChildren(); }

export function showAuth(mode = "welcome", opts = {}) {
  const box = screen(); box.hidden = false; box.replaceChildren();
  const card = h("div", { class: "authcard glass", role: "dialog", "aria-modal": "true", "aria-label": "FinBridge" });
  box.append(card);
  const brand = h("div", { class: "abrand" }, h("span", { class: "logo" }, "FinBridge"), h("small", {}, "BD"));
  const fail = errBox();
  const guard = (btn, label, fn) => async () => {
    fail.textContent = ""; setBusy(btn, true, label);
    try { await fn(); } catch (e) { fail.textContent = serverMsg(e.message); } finally { setBusy(btn, false, label); }
  };
  const check = (pairs) => {                       // pairs: [element, message-or-null]; shows the first problem
    let first = null;
    for (const [el, msg] of pairs) { invalid(el, !!msg); if (msg && !first) { first = [el, msg]; } }
    if (first) { fail.textContent = first[1]; first[0].focus(); throw new Error(first[1]); }
  };

  if (mode === "welcome") {
    card.append(brand, h("h1", {}, tr("w_title")), h("p", { class: "sub" }, tr("w_sub")),
      h("div", { class: "stack" },
        h("button", { class: "go wide", type: "button", onclick: () => showAuth("signin") }, tr("signin")),
        h("button", { class: "ghost wide", type: "button", onclick: () => showAuth("signup") }, tr("signup")),
        h("button", { class: "link", type: "button", onclick: () => { hideAuth(); hooks.onGuest(); } }, tr("guest_btn"))),
      langToggle());
    card.querySelector("button").focus();
    return;
  }

  if (mode === "signin") {
    const email = input({ type: "email", autocomplete: "username", required: true }), pw = input({ type: "password", autocomplete: "current-password", required: true });
    const btn = h("button", { class: "go wide", type: "submit" }, tr("signin"));
    const form = h("form", { novalidate: true, onsubmit: (e) => { e.preventDefault(); guard(btn, tr("signin"), async () => {
      check([[email, EMAIL.test(email.value.trim()) ? null : serverMsg("Enter a valid email address.")], [pw, pw.value ? null : tr("v_required", { f: tr("password") })]]);
      const r = await post("/api/auth/login", { email: email.value, password: pw.value }); finish(r);
    })(); } }, field(tr("email"), email), field(tr("password"), pw), fail, btn);
    card.append(brand, h("h1", {}, tr("signin")), form,
      h("div", { class: "row2" }, h("button", { class: "link", type: "button", onclick: () => showAuth("forgot") }, tr("forgot")),
        h("button", { class: "link", type: "button", onclick: () => showAuth("signup") }, tr("signup"))),
      h("button", { class: "link", type: "button", onclick: () => showAuth("welcome") }, "← " + tr("back")));
    email.focus(); return;
  }

  if (mode === "signup") {
    const name = input({ type: "text", autocomplete: "name", maxlength: 80 }), email = input({ type: "email", autocomplete: "username" });
    const pw = input({ type: "password", autocomplete: "new-password" }), pw2 = input({ type: "password", autocomplete: "new-password" });
    const terms = input({ type: "checkbox", id: "terms" });
    const btn = h("button", { class: "go wide", type: "submit" }, tr("signup"));
    const form = h("form", { novalidate: true, onsubmit: (e) => { e.preventDefault(); guard(btn, tr("signup"), async () => {
      check([[name, name.value.trim().length >= 2 ? null : tr("v_required", { f: tr("full_name") })], [email, EMAIL.test(email.value.trim()) ? null : serverMsg("Enter a valid email address.")],
        [pw, pwProblem(pw.value)], [pw2, pw.value === pw2.value ? null : serverMsg("Passwords do not match.")],
        [terms, terms.checked ? null : serverMsg("You must accept the privacy policy and terms to create an account.")]]);
      const r = await post("/api/auth/signup", { name: name.value, email: email.value, password: pw.value, confirm_password: pw2.value, accept_terms: terms.checked }); finish(r);
    })(); } },
      field(tr("full_name"), name), field(tr("email"), email), field(tr("password"), pw, tr("pw_hint")), field(tr("confirm_password"), pw2),
      h("div", { class: "chk" }, terms, h("label", { for: "terms" }, tr("accept"), " ", h("a", { href: "#", onclick: (e) => { e.preventDefault(); showPrivacy(); } }, tr("privacy_link")))),
      fail, btn);
    card.append(brand, h("h1", {}, tr("signup")), form,
      h("div", { class: "row2" }, h("span", { class: "sub" }, tr("have_account")), h("button", { class: "link", type: "button", onclick: () => showAuth("signin") }, tr("signin"))));
    name.focus(); return;
  }

  if (mode === "forgot") {
    const email = input({ type: "email", autocomplete: "username" }); const ok = h("div", { class: "note good", hidden: true });
    const btn = h("button", { class: "go wide", type: "submit" }, tr("send_link"));
    const form = h("form", { novalidate: true, onsubmit: (e) => { e.preventDefault(); guard(btn, tr("send_link"), async () => {
      check([[email, EMAIL.test(email.value.trim()) ? null : serverMsg("Enter a valid email address.")]]);
      const r = await post("/api/auth/forgot", { email: email.value }); ok.hidden = false; ok.textContent = r.message;
    })(); } }, field(tr("email"), email), fail, ok, btn);
    card.append(brand, h("h1", {}, tr("forgot_title")), form, h("button", { class: "link", type: "button", onclick: () => showAuth("signin") }, "← " + tr("back")));
    email.focus(); return;
  }

  if (mode === "reset") {
    const pw = input({ type: "password", autocomplete: "new-password" }), pw2 = input({ type: "password", autocomplete: "new-password" });
    const btn = h("button", { class: "go wide", type: "submit" }, tr("set_pw"));
    const form = h("form", { novalidate: true, onsubmit: (e) => { e.preventDefault(); guard(btn, tr("set_pw"), async () => {
      check([[pw, pwProblem(pw.value)], [pw2, pw.value === pw2.value ? null : serverMsg("Passwords do not match.")]]);
      const r = await post("/api/auth/reset", { token: opts.token, new_password: pw.value, confirm_password: pw2.value });
      history.replaceState(null, "", location.pathname); toast(r.message); showAuth("signin");
    })(); } }, field(tr("password"), pw, tr("pw_hint")), field(tr("confirm_password"), pw2), fail, btn);
    card.append(brand, h("h1", {}, tr("reset_title")), form); pw.focus();
  }

  function finish(r) {                      // success: store auth state and hand over to the app
    state.auth = r; state.csrf = r.csrf; hideAuth(); hooks.onAuth(r);
  }
}

function pwProblem(p) {
  if (p.length < 10) return serverMsg("Password must be at least 10 characters.");
  if (!/[A-Za-z]/.test(p) || !/\d/.test(p)) return serverMsg("Password must contain at least one letter and one digit.");
  return null;
}
function langToggle() {
  return h("button", { class: "link", type: "button", onclick: () => window.dispatchEvent(new CustomEvent("fb:toggle-lang")) }, "EN / বাংলা");
}

async function showPrivacy() {
  let text = "";
  try { text = (await get("/api/profile").catch(() => null))?.privacy; } catch (_) {}
  dialog({ title: tr("privacy_link"), content: h("p", { class: "confirmtext" }, text || FALLBACK_PRIVACY), actions: [{ label: tr("close"), cls: "go" }] });
}
const FALLBACK_PRIVACY = "FinBridge stores your profile and saved plans in this application's database. Financial fields are optional. We never ask for NID, passport, card numbers or bank passwords. If you use the AI assistant, only coarse hints (home currency, study country, university name) and your message text are sent to the AI provider. You can clear optional fields or delete your account and all its data at any time. This is a sandbox prototype: no real money is moved.";

export async function signOut() {
  try { await post("/api/auth/logout"); } catch (_) { /* cookie may already be gone */ }
  state.auth = null; state.csrf = null; hooks.onSignedOut(); toast(tr("signed_out"));
}

/* ------------------------------------------------------------------ profile */
export async function openProfile() {
  const body = h("div", {}, h("div", { class: "skel" }, h("i"), h("i"), h("i")));
  const dlg = dialog({ title: tr("p_title"), content: body, wide: true });
  let data;
  try { data = await get("/api/profile"); } catch (e) { body.replaceChildren(h("div", { class: "err" }, serverMsg(e.message), " ", h("button", { class: "link", onclick: () => { dlg.close(); openProfile(); } }, tr("retry")))); return; }
  const p = data.profile;
  const f = {
    home: input({ type: "text", list: "countryList", maxlength: 60, value: p.home_country || "" }), study: input({ type: "text", list: "countryList", maxlength: 60, value: p.study_country || "" }),
    lang: select([["en", "English"], ["bn", "বাংলা"]], p.language), ccy: select(CCY.map((c) => [c, c]), p.currency),
    tz: select([...new Set([p.timezone, ...TIMEZONES])].map((z) => [z, z]), p.timezone),
    level: select([["", "—"], ...["school", "foundation", "bachelor", "master", "phd", "other"].map((k) => [k, levelName(k)])], p.study_level || ""),
    prog: input({ type: "text", maxlength: 100, value: p.program || "" }),
    inc: input({ type: "number", min: 0, step: "any", inputmode: "decimal", value: p.monthly_income ?? "" }), bud: input({ type: "number", min: 0, step: "any", inputmode: "decimal", value: p.monthly_budget ?? "" }),
    tdate: input({ type: "date", value: p.tuition_date || "" }),
    r1: input({ type: "checkbox", id: "r1", ...(p.remind_tuition ? { checked: true } : {}) }), r2: input({ type: "checkbox", id: "r2", ...(p.remind_budget ? { checked: true } : {}) }), r3: input({ type: "checkbox", id: "r3", ...(p.remind_savings ? { checked: true } : {}) }),
  };
  f.r1.checked = p.remind_tuition; f.r2.checked = p.remind_budget; f.r3.checked = p.remind_savings;
  const uni = universityPicker(p);
  const fail = errBox();
  const save = h("button", { class: "go", type: "button" }, tr("save"));
  save.onclick = async () => {
    fail.textContent = ""; setBusy(save, true, tr("save"));
    const num = (el) => (el.value === "" ? null : Number(el.value));
    try {
      const r = await put("/api/profile", { home_country: f.home.value || null, study_country: f.study.value || null, language: f.lang.value, currency: f.ccy.value, timezone: f.tz.value,
        study_level: f.level.value || null, program: f.prog.value || null, monthly_income: num(f.inc), monthly_budget: num(f.bud), tuition_date: f.tdate.value || null,
        remind_tuition: f.r1.checked, remind_budget: f.r2.checked, remind_savings: f.r3.checked, ...uni.value() });
      state.auth.profile = r.profile; hooks.onProfile(r.profile); toast(tr("saved_ok")); dlg.close();
    } catch (e) { fail.textContent = serverMsg(e.message); } finally { setBusy(save, false, tr("save")); }
  };
  const clear = h("button", { class: "ghost", type: "button", onclick: async () => {
    if (!await confirmBox(tr("clear_optional"), tr("clear_optional"))) return;
    try { const r = await del("/api/profile"); state.auth.profile = r.profile; hooks.onProfile(r.profile); toast(tr("saved_ok")); dlg.close(); } catch (e) { toast(serverMsg(e.message), "err"); }
  } }, tr("clear_optional"));
  const del_ = h("button", { class: "ghost danger", type: "button", onclick: () => deleteAccount(dlg) }, tr("delete_account"));
  body.replaceChildren(
    h("div", { class: "grid2" }, field(tr("email"), input({ value: state.auth.user.email, readonly: true, disabled: true })), field(tr("full_name"), input({ value: state.auth.user.name, readonly: true, disabled: true }))),
    h("datalist", { id: "countryList" }, ...COUNTRY_NAMES.map((n) => h("option", { value: n }))), h("div", { class: "grid2" }, field(tr("home_country"), f.home), field(tr("study_country"), f.study)),
    h("div", { class: "grid3" }, field(tr("language"), f.lang), field(tr("currency"), f.ccy), field(tr("timezone"), f.tz)),
    h("h3", { class: "sect" }, tr("uni_card")), uni.el,
    h("div", { class: "grid2" }, field(tr("study_level"), f.level), field(tr("program"), f.prog)),
    h("div", { class: "grid3" }, field(tr("monthly_income"), f.inc), field(tr("monthly_budget"), f.bud), field(tr("tuition_date"), f.tdate)),
    h("h3", { class: "sect" }, tr("rem_title")),
    h("div", { class: "chkrow" }, h("span", { class: "chk" }, f.r1, h("label", { for: "r1" }, tr("rem_tuition"))), h("span", { class: "chk" }, f.r2, h("label", { for: "r2" }, tr("rem_budget"))), h("span", { class: "chk" }, f.r3, h("label", { for: "r3" }, tr("rem_savings")))),
    h("p", { class: "sub" }, tr("rem_note")), h("p", { class: "sub privacy" }, data.privacy), fail,
    h("div", { class: "actions spread" }, h("div", { class: "left" }, clear, del_), h("div", {}, h("button", { class: "ghost", type: "button", onclick: () => dlg.close() }, tr("cancel")), save)));
}

function universityPicker(p) {
  let selected = p.university_id ? { id: p.university_id, name: p.uni_name, country: p.uni_country, city: p.uni_city } : null;
  let other = p.university_other || "";
  const q = input({ type: "search", placeholder: tr("uni_search"), "aria-label": tr("uni_search") });
  const country = select([["", tr("all_countries")]]); country.setAttribute("aria-label", tr("uni_country"));
  const list = h("div", { class: "unilist", role: "listbox", "aria-label": tr("uni_card") });
  const otherIn = input({ type: "text", maxlength: 100, value: other, placeholder: tr("uni_other_name") });
  const cur = h("div", { class: "unicur" });
  const note = h("p", { class: "sub" }, tr("uni_note"));
  let timer, seq = 0, loaded = false;
  const paintCur = () => cur.replaceChildren(selected ? h("span", {}, "✓ ", h("b", {}, selected.name), ` · ${selected.city ? selected.city + ", " : ""}${selected.country}`, " ", h("small", {}, `(${tr("uni_sample")})`))
    : other ? h("span", {}, "✓ ", h("b", {}, other), " ", h("small", {}, `(${tr("uni_other")})`)) : h("span", { class: "sub" }, tr("no_uni")));
  const search = async () => {
    const my = ++seq;
    try {
      const r = await get(`/api/universities?${new URLSearchParams({ q: q.value, country: country.value, limit: 12 })}`);
      if (my !== seq) return;
      if (!loaded) { loaded = true; r.countries.forEach((c) => country.append(h("option", { value: c }, c))); }
      list.replaceChildren(...r.items.map((u) => h("button", { type: "button", role: "option", class: "uni" + (selected && selected.id === u.id ? " on" : ""), "aria-selected": selected && selected.id === u.id,
        onclick: () => { selected = u; other = ""; otherIn.value = ""; paintCur(); search(); } }, h("b", {}, u.name), h("span", {}, `${u.city || ""} · ${u.country}`))),
        h("button", { type: "button", role: "option", class: "uni other", onclick: () => { selected = null; otherIn.focus(); paintCur(); } }, h("b", {}, tr("uni_other"))));
    } catch (e) { list.replaceChildren(h("div", { class: "err" }, serverMsg(e.message))); }
  };
  q.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(search, 200); });
  country.addEventListener("change", search);
  otherIn.addEventListener("input", () => { other = otherIn.value.trim(); if (other) selected = null; paintCur(); });
  paintCur(); search();
  return {
    el: h("div", { class: "unipick" }, cur, h("div", { class: "grid2" }, q, country), list, field(tr("uni_other_name"), otherIn), note),
    value: () => (selected ? { university_id: selected.id } : other ? { university_id: null, university_other: other } : {}),
  };
}

async function deleteAccount(parent) {
  const pw = input({ type: "password", autocomplete: "current-password" }); const fail = errBox();
  const dlg = dialog({ title: tr("delete_account"), content: h("div", {}, h("p", { class: "confirmtext" }, tr("delete_pw")), field(tr("password"), pw), fail),
    actions: [{ label: tr("cancel") }, { label: tr("delete"), cls: "go danger", onClick: async () => {
      try { await post("/api/account/delete", { password: pw.value }); state.auth = null; state.csrf = null; dlg.close(); parent.close(); hooks.onSignedOut(); toast(tr("deleted_ok")); }
      catch (e) { fail.textContent = serverMsg(e.message); } } }] });
}

/* ------------------------------------------------------------------ wallet */
export function openWallet(onChange) {
  let kind = "add";
  const amount = input({ type: "number", min: 0, step: "any", inputmode: "decimal" });
  const ccy = select(CCY.map((c) => [c, c]), state.auth?.profile?.currency || "BDT");
  const secret = input({ type: "password", autocomplete: signedIn() ? "current-password" : "off" });
  const fail = errBox(); const ok = h("div", { class: "note good", hidden: true });
  const secretField = field(signedIn() ? tr("w_pw") : tr("w_pin"), secret);
  const go = h("button", { class: "go", type: "button" }, tr("save"));
  const tabs = h("div", { class: "tabs mini" }, ["add", "withdraw"].map((k) => h("button", { type: "button", role: "tab", "aria-selected": k === kind, onclick: () => { kind = k; [...tabs.children].forEach((b, i) => b.setAttribute("aria-selected", ["add", "withdraw"][i] === k)); secretField.hidden = k === "add"; go.textContent = k === "add" ? tr("w_add") : tr("w_withdraw"); } }, k === "add" ? tr("w_add") : tr("w_withdraw"))));
  secretField.hidden = true; go.textContent = tr("w_add");
  const dlg = dialog({ title: tr("wallet"), content: h("div", {}, h("p", { class: "sub" }, tr("w_note")), tabs, field(tr("amount"), amount), field(tr("currency"), ccy), secretField, fail, ok),
    actions: [{ label: tr("close") }, { label: "", cls: "go", onClick: null }] });
  dlg.foot.lastChild.replaceWith(go);
  go.onclick = async () => {
    fail.textContent = ""; ok.hidden = true;
    const a = Number(amount.value);
    if (!(a > 0)) { fail.textContent = tr("amount") + " > 0"; invalid(amount, true); amount.focus(); return; }
    setBusy(go, true); const label = kind === "add" ? tr("w_add") : tr("w_withdraw");
    try {
      const body = { amount: a, currency: ccy.value, session_id: state.sessionId };
      const r = kind === "add" ? await post("/api/wallet/deposit", body) : await post("/api/wallet/withdraw", { ...body, secret: secret.value });
      if (r.session_id && !signedIn()) state.sessionId = r.session_id;
      ok.hidden = false; ok.textContent = `${r.entry.ref}: ${money(r.entry.amount, r.entry.currency)} (${r.entry.status})`; secret.value = ""; amount.value = ""; onChange(r.balances);
    } catch (e) { fail.textContent = serverMsg(e.message); } finally { setBusy(go, false); go.textContent = label; }
  };
}

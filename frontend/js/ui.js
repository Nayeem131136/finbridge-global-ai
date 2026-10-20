/* Small UI kit: toasts, accessible dialogs, confirm box, form helpers. All text via textContent (no innerHTML). */
import { h } from "./cards.js";
import { tr } from "./i18n.js";

export const CCY = ["BDT", "USD", "GBP", "EUR", "AUD", "CAD", "CNY", "MYR", "SGD", "JPY", "INR", "AED"];
export const TIMEZONES = ["Asia/Dhaka", "Europe/London", "Europe/Berlin", "America/New_York", "America/Chicago", "America/Los_Angeles", "America/Toronto", "Australia/Sydney", "Australia/Melbourne", "Asia/Shanghai", "Asia/Kuala_Lumpur", "Asia/Singapore", "Asia/Tokyo", "Asia/Kolkata", "Asia/Dubai", "UTC"];

let toastBox;
export function toast(msg, kind = "ok") {
  toastBox ||= document.body.appendChild(h("div", { class: "toasts", "aria-live": "polite", role: "status" }));
  const t = h("div", { class: `toast ${kind}` }, msg);
  toastBox.append(t);
  setTimeout(() => t.remove(), kind === "err" ? 6500 : 3800);
}

const openDialogs = [];
export function dialog({ title, content, actions = [], wide = false, onClose } = {}) {
  const prev = document.activeElement;
  const id = "dlg" + Math.random().toString(36).slice(2, 7);
  const close = () => {
    el.remove(); openDialogs.splice(openDialogs.indexOf(api), 1);
    if (prev && prev.focus) prev.focus();
    if (onClose) onClose();
  };
  const foot = h("div", { class: "actions" }, actions.map((a) => h("button", { type: "button", class: a.cls || "ghost", onclick: () => a.onClick ? a.onClick(api) : close() }, a.label)));
  const el = h("div", { class: "modal dyn", role: "dialog", "aria-modal": "true", "aria-labelledby": id, onclick: (e) => { if (e.target === el) close(); } },
    h("div", { class: "sheet glass" + (wide ? " wide" : "") },
      h("div", { class: "dhead" }, h("h2", { id }, title), h("button", { class: "x", type: "button", "aria-label": tr("close"), onclick: close }, "×")),
      h("div", { class: "dbody" }, content), actions.length ? foot : null));
  const api = { el, close, body: el.querySelector(".dbody"), foot };
  document.body.append(el); openDialogs.push(api);
  setTimeout(() => (el.querySelector("input,select,textarea,button:not(.x)") || el).focus(), 30);
  return api;
}
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && openDialogs.length) openDialogs[openDialogs.length - 1].close(); });

export function confirmBox(message, okLabel) {
  return new Promise((resolve) => {
    let done = false;
    const finish = (v, d) => { if (!done) { done = true; resolve(v); } d.close(); };
    dialog({ title: "", content: h("p", { class: "confirmtext" }, message), onClose: () => { if (!done) { done = true; resolve(false); } },
      actions: [{ label: tr("cancel"), onClick: (d) => finish(false, d) }, { label: okLabel || tr("delete"), cls: "go danger", onClick: (d) => finish(true, d) }] });
  });
}

let uid = 0;
export function field(label, input, hint) {
  const id = input.id || (input.id = "f" + ++uid);
  return h("div", { class: "fld" }, h("label", { for: id }, label), input, hint ? h("div", { class: "hintline", id: id + "h" }, hint) : null);
}
export const input = (attrs) => h("input", { autocomplete: "off", ...attrs });
export function select(options, value) {
  const s = h("select", {}, options.map(([v, l]) => h("option", { value: v }, l)));
  if (value !== undefined && value !== null) s.value = value;
  return s;
}
export function setBusy(btn, busy, label) {
  btn.disabled = busy; btn.setAttribute("aria-busy", busy);
  if (label !== undefined) btn.textContent = busy ? tr("working") : label;
}
export function errBox() { return h("div", { class: "err", role: "alert" }); }
export function skeleton(lines = 3) { return h("div", { class: "skel" }, Array.from({ length: lines }, () => h("i"))); }
export function invalid(el, on) { if (el) { el.setAttribute("aria-invalid", on ? "true" : "false"); } }

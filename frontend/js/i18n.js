/* English / Bangla strings for the account, dashboard and plans screens: S[key] = [en, bn].
   Missing Bangla falls back to English. API field names and currency codes are never translated. */
import { state } from "./api.js";

const S = {
  tab_home: ["Home", "হোম"], tab_plans: ["My plans", "আমার পরিকল্পনা"], tab_chat: ["Assistant", "সহকারী"], tab_explore: ["Cost Explorer", "খরচ হিসাব"],
  signin: ["Sign in", "সাইন ইন"], signup: ["Create account", "অ্যাকাউন্ট খুলুন"], signout: ["Sign out", "সাইন আউট"], profile: ["Profile", "প্রোফাইল"],
  wallet: ["Wallet", "ওয়ালেট"], guest: ["Demo guest", "ডেমো অতিথি"], guest_note: ["Demo guest: nothing is saved. Sign in to keep your plans.", "ডেমো অতিথি: কিছু সংরক্ষিত হয় না। পরিকল্পনা রাখতে সাইন ইন করুন।"],
  w_title: ["Welcome to FinBridge", "FinBridge-এ স্বাগতম"], w_sub: ["Sign in to save budgets and tuition plans, or try the sandbox as a guest.", "বাজেট ও টিউশন পরিকল্পনা সংরক্ষণ করতে সাইন ইন করুন, অথবা অতিথি হিসেবে স্যান্ডবক্স ঘুরে দেখুন।"],
  guest_btn: ["Continue as demo guest", "ডেমো অতিথি হিসেবে চালিয়ে যান"],
  email: ["Email", "ইমেইল"], password: ["Password", "পাসওয়ার্ড"], confirm_password: ["Confirm password", "পাসওয়ার্ড আবার দিন"], full_name: ["Full name", "পুরো নাম"],
  accept: ["I agree to the privacy policy and terms (sandbox prototype, no real money).", "আমি গোপনীয়তা নীতি ও শর্তে সম্মত (স্যান্ডবক্স প্রোটোটাইপ, আসল টাকা নয়)।"],
  pw_hint: ["At least 10 characters with a letter and a digit.", "কমপক্ষে ১০ অক্ষর, একটি অক্ষর ও একটি সংখ্যা সহ।"],
  forgot: ["Forgot password?", "পাসওয়ার্ড ভুলে গেছেন?"], send_link: ["Send reset link", "রিসেট লিংক পাঠান"], back: ["Back", "ফিরে যান"],
  reset_title: ["Choose a new password", "নতুন পাসওয়ার্ড দিন"], set_pw: ["Set password", "পাসওয়ার্ড সেট করুন"], forgot_title: ["Reset your password", "পাসওয়ার্ড রিসেট করুন"],
  no_account: ["No account yet?", "অ্যাকাউন্ট নেই?"], have_account: ["Already have an account?", "আগেই অ্যাকাউন্ট আছে?"],
  privacy_link: ["Privacy information", "গোপনীয়তা তথ্য"], working: ["Working…", "অপেক্ষা করুন…"],
  welcome_back: ["Welcome back, {name}", "আবার স্বাগতম, {name}"], loading: ["Loading…", "লোড হচ্ছে…"],
  retry: ["Try again", "আবার চেষ্টা করুন"], load_err: ["Could not load this section.", "এই অংশ লোড করা যায়নি।"],
  uni_card: ["Your university", "আপনার বিশ্ববিদ্যালয়"], no_uni: ["No university selected yet.", "এখনো কোনো বিশ্ববিদ্যালয় বাছা হয়নি।"], pick_uni: ["Choose in profile", "প্রোফাইলে বাছুন"],
  uni_note: ["Selecting a university does not verify enrollment. Confirm payment details on its official website.", "বিশ্ববিদ্যালয় বাছলে ভর্তি যাচাই হয় না। পেমেন্টের তথ্য তাদের অফিসিয়াল ওয়েবসাইটে নিশ্চিত করুন।"],
  budget_card: ["Monthly budget", "মাসিক বাজেট"], no_budget: ["No budget saved yet. Create one in My plans.", "এখনো বাজেট সংরক্ষিত নেই। “আমার পরিকল্পনা”-য় একটি তৈরি করুন।"],
  income: ["Income", "আয়"], expenses: ["Expenses", "খরচ"], left_over: ["Left over", "উদ্বৃত্ত"], savings_rate: ["Savings rate", "সঞ্চয়ের হার"],
  savings_card: ["Tuition savings progress", "টিউশন সঞ্চয়ের অগ্রগতি"], no_tuition: ["No tuition plan yet. Create one in My plans.", "এখনো টিউশন পরিকল্পনা নেই। “আমার পরিকল্পনা”-য় তৈরি করুন।"],
  deadlines: ["Upcoming tuition deadlines", "আসন্ন টিউশন সময়সীমা"], no_deadlines: ["No upcoming deadlines.", "কোনো আসন্ন সময়সীমা নেই।"], days_left: ["{n} day(s) left", "আর {n} দিন বাকি"],
  saved_cmp: ["Saved comparisons", "সংরক্ষিত তুলনা"], no_cmp: ["Save a comparison from the Assistant or Cost Explorer.", "সহকারী বা খরচ হিসাব থেকে তুলনা সংরক্ষণ করুন।"],
  activity: ["Recent activity (sandbox)", "সাম্প্রতিক কার্যকলাপ (স্যান্ডবক্স)"], no_activity: ["No sandbox activity yet.", "এখনো স্যান্ডবক্স কার্যকলাপ নেই।"],
  reminders: ["Reminders", "রিমাইন্ডার"], no_reminders: ["No reminders right now.", "এখন কোনো রিমাইন্ডার নেই।"], dismiss: ["Dismiss", "সরান"],
  rem_note: ["Shown in the app only. No email or push message is sent.", "শুধু অ্যাপে দেখানো হয়। কোনো ইমেইল বা পুশ বার্তা পাঠানো হয় না।"],
  quick: ["Quick actions", "দ্রুত কাজ"], qa_compare: ["Compare routes", "রুট তুলনা"], qa_budget: ["Build a budget", "বাজেট বানান"], qa_tuition: ["Tuition plan", "টিউশন পরিকল্পনা"],
  qa_invoice: ["Check an invoice", "ইনভয়েস যাচাই"], qa_ask: ["Ask the assistant", "সহকারীকে জিজ্ঞেস করুন"], qa_plans: ["Saved plans & activity", "সংরক্ষিত পরিকল্পনা ও কার্যকলাপ"],
  disclaimer: ["Estimates use what you entered and illustrative sandbox data. Not financial advice; no real payment was made.", "হিসাব আপনার দেওয়া তথ্য ও কাল্পনিক স্যান্ডবক্স ডেটার ওপর নির্ভর করে। আর্থিক পরামর্শ নয়; কোনো আসল পেমেন্ট হয়নি।"],
  new_budget: ["New budget", "নতুন বাজেট"], new_tuition: ["New tuition plan", "নতুন টিউশন পরিকল্পনা"], budgets: ["Budgets", "বাজেট"], tuition_plans: ["Tuition plans", "টিউশন পরিকল্পনা"],
  edit: ["Edit", "সম্পাদনা"], delete: ["Delete", "মুছুন"], open_chat: ["Ask the assistant", "সহকারীকে জিজ্ঞেস করুন"], cancel: ["Cancel", "বাতিল"], save: ["Save", "সংরক্ষণ"], close: ["Close", "বন্ধ"],
  confirm_delete: ["Delete “{name}”? This cannot be undone.", "“{name}” মুছবেন? এটি ফেরানো যাবে না।"],
  name: ["Name", "নাম"], category: ["Category", "খাত"], amount: ["Amount", "পরিমাণ"], add_expense: ["Add expense", "খরচ যোগ করুন"], target: ["Savings goal (%)", "সঞ্চয়ের লক্ষ্য (%)"],
  total: ["Tuition total", "মোট টিউশন"], tcurrency: ["Tuition currency", "টিউশনের মুদ্রা"], due_dates: ["Due dates (one per line, YYYY-MM-DD)", "পরিশোধের তারিখ (প্রতি লাইনে একটি, YYYY-MM-DD)"],
  home_ccy: ["Your currency", "আপনার মুদ্রা"], saved_so_far: ["Saved so far (your currency)", "এ পর্যন্ত জমা (আপনার মুদ্রায়)"], monthly_saving: ["Planned monthly saving (optional)", "মাসিক সঞ্চয়ের পরিকল্পনা (ঐচ্ছিক)"],
  progress: ["Progress", "অগ্রগতি"], shortfall: ["Estimated shortfall per month", "মাসিক ঘাটতির আনুমানিক পরিমাণ"], on_track: ["On track by your inputs", "আপনার তথ্য অনুযায়ী ঠিক পথে"],
  past_dues: ["All due dates are in the past.", "সব তারিখ পেরিয়ে গেছে।"], next_due: ["Next due", "পরবর্তী তারিখ"], save_cmp: ["Save this comparison", "এই তুলনা সংরক্ষণ করুন"],
  saved_ok: ["Saved.", "সংরক্ষিত হয়েছে।"], deleted_ok: ["Deleted.", "মুছে ফেলা হয়েছে।"], signed_out: ["You have been signed out.", "আপনি সাইন আউট হয়েছেন।"],
  need_signin: ["Sign in to save this.", "এটি সংরক্ষণ করতে সাইন ইন করুন।"],
  p_title: ["Your profile", "আপনার প্রোফাইল"], home_country: ["Home country", "নিজ দেশ"], study_country: ["Study country", "পড়াশোনার দেশ"], language: ["Interface language", "ইন্টারফেসের ভাষা"],
  currency: ["Preferred currency", "পছন্দের মুদ্রা"], timezone: ["Time zone", "সময় অঞ্চল"], study_level: ["Study level", "পড়াশোনার স্তর"], program: ["Degree or program", "ডিগ্রি বা প্রোগ্রাম"],
  monthly_income: ["Monthly income (optional)", "মাসিক আয় (ঐচ্ছিক)"], monthly_budget: ["Monthly budget (optional)", "মাসিক বাজেট (ঐচ্ছিক)"], tuition_date: ["Expected tuition payment date (optional)", "টিউশন পরিশোধের সম্ভাব্য তারিখ (ঐচ্ছিক)"],
  uni_search: ["Search universities", "বিশ্ববিদ্যালয় খুঁজুন"], uni_country: ["Country", "দেশ"], all_countries: ["All countries", "সব দেশ"], uni_other: ["Other / not listed", "অন্যান্য / তালিকায় নেই"],
  uni_other_name: ["University name (if not listed)", "বিশ্ববিদ্যালয়ের নাম (তালিকায় না থাকলে)"], uni_sample: ["Sample directory entry: name and location only.", "নমুনা তালিকা: শুধু নাম ও অবস্থান।"],
  rem_title: ["Reminder preferences", "রিমাইন্ডারের পছন্দ"], rem_tuition: ["Tuition deadlines", "টিউশনের সময়সীমা"], rem_budget: ["Budget review", "বাজেট পর্যালোচনা"], rem_savings: ["Savings milestones", "সঞ্চয়ের মাইলফলক"],
  clear_optional: ["Clear optional fields", "ঐচ্ছিক তথ্য মুছুন"], delete_account: ["Delete my account and data", "আমার অ্যাকাউন্ট ও তথ্য মুছুন"], delete_pw: ["Enter your password to delete your account permanently.", "অ্যাকাউন্ট স্থায়ীভাবে মুছতে পাসওয়ার্ড দিন।"],
  levels: [{ school: "School", foundation: "Foundation", bachelor: "Bachelor", master: "Master", phd: "PhD", other: "Other" }, { school: "স্কুল", foundation: "ফাউন্ডেশন", bachelor: "ব্যাচেলর", master: "মাস্টার্স", phd: "পিএইচডি", other: "অন্যান্য" }],
  w_add: ["Add money (sandbox)", "টাকা যোগ করুন (স্যান্ডবক্স)"], w_withdraw: ["Withdraw (sandbox)", "টাকা তুলুন (স্যান্ডবক্স)"], w_source: ["Source", "উৎস"],
  w_note: ["Simulated money only. Deposits and withdrawals are done by you, never by the AI.", "শুধু কাল্পনিক টাকা। জমা ও উত্তোলন আপনি করেন, AI কখনো নয়।"],
  w_pw: ["Confirm with your password", "পাসওয়ার্ড দিয়ে নিশ্চিত করুন"], w_pin: ["Confirm with the demo PIN (1234, development only)", "ডেমো PIN দিয়ে নিশ্চিত করুন (1234, শুধু ডেভেলপমেন্টের জন্য)"],
  confirm_pw_label: ["Enter your account password to confirm", "নিশ্চিত করতে অ্যাকাউন্টের পাসওয়ার্ড দিন"],
  inv_upload: ["Upload a text-based PDF invoice", "টেক্সটযুক্ত PDF ইনভয়েস আপলোড করুন"], inv_note: ["Risk indicators are hints, not proof of fraud. Verify beneficiary details through the university's official channel.", "ঝুঁকির ইঙ্গিত প্রমাণ নয়। বিশ্ববিদ্যালয়ের অফিসিয়াল মাধ্যমে প্রাপকের তথ্য যাচাই করুন।"],
  best: ["Best", "সেরা"], monthly_cap: ["Most you can save per month (optional)", "মাসে সর্বোচ্চ কত জমাতে পারবেন (ঐচ্ছিক)"], monthly_need: ["Needed per month", "মাসে প্রয়োজন"],
  send_to_checker: ["Check invoice", "ইনভয়েস যাচাই করুন"], account: ["Account", "অ্যাকাউন্ট"], guest_cmp: ["Sign in to save comparisons.", "তুলনা সংরক্ষণ করতে সাইন ইন করুন।"],
  m_pw_label: ["Enter your account password to confirm", "নিশ্চিত করতে অ্যাকাউন্টের পাসওয়ার্ড দিন"], session_expired: ["Your session expired. Please sign in again.", "সেশন শেষ হয়েছে। আবার সাইন ইন করুন।"],
  v_required: ["{f} is required.", "{f} দিতে হবে।"],
  skip: ["Skip to content", "মূল অংশে যান"],
  tab_study: ["Study plan", "পড়াশোনার পরিকল্পনা"], sp_new: ["New study plan", "নতুন পরিকল্পনা"], sp_intro: ["Estimate what studying abroad will cost and how much is still unfunded. Everything is calculated from the numbers you enter.", "বিদেশে পড়ার খরচ আর কতটা অর্থায়ন বাকি তার হিসাব। সব হিসাব আপনার দেওয়া সংখ্যা থেকে।"],
  sp_empty: ["No study plan yet. Create one to see your funding gap.", "এখনো কোনো পরিকল্পনা নেই। ঘাটতি দেখতে একটি বানান।"], sp_open: ["Open", "খুলুন"], sp_dup: ["Duplicate", "কপি"], sp_pdf: ["PDF report", "PDF রিপোর্ট"], sp_compare: ["Compare selected (2-3)", "নির্বাচিতগুলো তুলনা (২-৩টি)"],
  sp_dest: ["Destination country", "গন্তব্য দেশ"], sp_uni: ["University (type or pick)", "বিশ্ববিদ্যালয় (লিখুন বা বাছুন)"], sp_years: ["Duration (years)", "মেয়াদ (বছর)"], sp_tuition: ["Tuition per year", "বছরে টিউশন"], sp_living: ["Living cost per month", "মাসিক বসবাস খরচ"],
  sp_onetime: ["One-time costs (visa, flights, deposit)", "এককালীন খরচ (ভিসা, ফ্লাইট, জমা)"], sp_confirmed: ["Confirmed funding (family, loan, confirmed scholarship)", "নিশ্চিত অর্থায়ন (পরিবার, ঋণ, নিশ্চিত বৃত্তি)"], sp_potential: ["Potential scholarships (NOT confirmed)", "সম্ভাব্য বৃত্তি (নিশ্চিত নয়)"],
  sp_savings: ["Current savings", "বর্তমান সঞ্চয়"], sp_capacity: ["Savings per month you can add", "মাসে যত জমাতে পারবেন"], sp_target: ["Target date (start of study)", "লক্ষ্য তারিখ (পড়া শুরু)"], sp_tg: ["Tuition growth %/year", "টিউশন বৃদ্ধি %/বছর"], sp_lg: ["Living-cost growth %/year", "খরচ বৃদ্ধি %/বছর"],
  r_total: ["Total estimated cost", "মোট আনুমানিক খরচ"], r_confirmed: ["Confirmed money", "নিশ্চিত অর্থ"], r_gap: ["Confirmed gap", "নিশ্চিত ঘাটতি"], r_pgap: ["Gap if potential funding arrives", "সম্ভাব্য অর্থ এলে ঘাটতি"], r_cov: ["Covered by confirmed money", "নিশ্চিত অর্থে কভার"], r_monthly: ["Save per month to close the gap", "ঘাটতি মেটাতে মাসে জমান"], r_months: ["months to target", "লক্ষ্য পর্যন্ত মাস"],
  r_tuition: ["Tuition", "টিউশন"], r_living: ["Living", "বসবাস"], r_other: ["One-time", "এককালীন"], r_potential_note: ["Potential funding is shown separately and is never counted as confirmed.", "সম্ভাব্য অর্থ আলাদা দেখানো হয়, নিশ্চিত হিসেবে ধরা হয় না।"],
  fx_sens: ["If costs move by…", "খরচ বদলালে…"], whatif: ["What-if lab", "হোয়াট-ইফ ল্যাব"], wi_t: ["Tuition change %", "টিউশন পরিবর্তন %"], wi_l: ["Living change %", "বসবাস খরচ পরিবর্তন %"], wi_x: ["Extra confirmed funding", "অতিরিক্ত নিশ্চিত অর্থ"], wi_run: ["Calculate scenario", "দৃশ্যপট হিসাব করুন"], wi_note: ["Scenario only, nothing is saved.", "শুধু দৃশ্যপট, কিছু সংরক্ষিত হয় না।"], wi_change: ["Change in confirmed gap", "নিশ্চিত ঘাটতির পরিবর্তন"],
  quotes: ["Bank and provider rate board (entered by you)", "ব্যাংক ও প্রোভাইডার রেট বোর্ড (আপনার দেওয়া)"], q_note: ["Type the rate you see on your bank's or provider's own website, with the time you saw it. FinBridge does not fetch bank prices; it compares your rate with the market reference rate.", "আপনার ব্যাংক বা প্রোভাইডারের ওয়েবসাইটে দেখা রেট ও সময় লিখুন। FinBridge ব্যাংকের দাম আনে না; আপনার রেটকে বাজার রেফারেন্সের সাথে তুলনা করে।"], q_provider: ["Provider (your label)", "প্রোভাইডার (আপনার নাম)"], q_amount: ["Amount to send", "পাঠানোর পরিমাণ"], q_rate: ["Rate (receive per 1 sent)", "রেট (১ এককে যত পাবেন)"], q_fee: ["Fee %", "ফি %"], q_fixed: ["Fixed fee", "নির্দিষ্ট ফি"], q_conv: ["Fee is…", "ফি…"], q_added: ["added on top", "অতিরিক্ত যুক্ত"], q_included: ["taken from amount", "পরিমাণ থেকে কাটা"], q_from: ["Send currency", "পাঠানোর মুদ্রা"], q_to: ["Receive currency", "প্রাপ্তির মুদ্রা"], q_add: ["Add quote", "কোট যোগ করুন"], q_paid: ["You pay", "আপনি দেবেন"], q_gets: ["Recipient gets", "প্রাপক পাবে"], q_best: ["Best value", "সেরা মান"], q_asof: ["Rate as of", "রেটের সময়"], q_saved_time: ["time you saved it", "সংরক্ষণের সময়"], q_rate_short: ["rate", "রেট"], q_stale: ["Over 24h old: re-check", "২৪ ঘণ্টার বেশি পুরনো: আবার দেখুন"], q_when: ["When did you see this rate?", "এই রেট কখন দেখেছেন?"], q_market: ["Market rate", "বাজার রেট"], q_live: ["live", "লাইভ"], q_sample: ["fixed sample", "নমুনা রেট"], q_below: ["below market", "বাজার রেটের নিচে"], q_above: ["above market", "বাজার রেটের উপরে"], q_same_market: ["Same as market", "বাজার রেটের সমান"],
  checklist: ["Checklist", "চেকলিস্ট"], ck_add: ["Add item", "আইটেম যোগ"], ck_ph: ["New checklist item", "নতুন আইটেম"], scholarships: ["Scholarship directory", "বৃত্তির তালিকা"], sch_note: ["Directory only: no amounts or eligibility. Verify on the official site.", "শুধু তালিকা: পরিমাণ বা যোগ্যতা নেই। অফিসিয়াল সাইটে যাচাই করুন।"], sch_open: ["Official site", "অফিসিয়াল সাইট"],
  sp_explain: ["Ask the AI to explain this plan", "AI-কে এই পরিকল্পনা বোঝাতে বলুন"], compare_title: ["Plan comparison", "পরিকল্পনার তুলনা"], compare_pick: ["Select 2 or 3 plans to compare.", "তুলনার জন্য ২-৩টি পরিকল্পনা বাছুন।"], compare_cur: ["Plans in different currencies are not converted.", "ভিন্ন মুদ্রার পরিকল্পনা রূপান্তর করা হয় না।"],
};
// Common server messages, translated by exact match. Anything else is shown in English.
const SERVER = {
  "Wrong email or password.": "ইমেইল বা পাসওয়ার্ড ভুল।",
  "Passwords do not match.": "পাসওয়ার্ড দুটি মিলছে না।",
  "An account with this email already exists. Try signing in.": "এই ইমেইলে আগেই অ্যাকাউন্ট আছে। সাইন ইন করে দেখুন।",
  "Password must be at least 10 characters.": "পাসওয়ার্ড কমপক্ষে ১০ অক্ষরের হতে হবে।",
  "Password must contain at least one letter and one digit.": "পাসওয়ার্ডে অন্তত একটি অক্ষর ও একটি সংখ্যা থাকতে হবে।",
  "Enter a valid email address.": "সঠিক ইমেইল ঠিকানা দিন।",
  "You must accept the privacy policy and terms to create an account.": "অ্যাকাউন্ট খুলতে গোপনীয়তা নীতি ও শর্তে সম্মত হতে হবে।",
  "Please sign in.": "অনুগ্রহ করে সাইন ইন করুন।",
  "Too many failed attempts. Please wait a few minutes and try again.": "অনেকবার ভুল হয়েছে। কয়েক মিনিট পরে আবার চেষ্টা করুন।",
  "Cannot reach the server. Check that it is running, then try again.": "সার্ভারে সংযোগ করা যাচ্ছে না। সার্ভার চালু আছে কিনা দেখে আবার চেষ্টা করুন।",
  "Something went wrong on the server. Please try again.": "সার্ভারে সমস্যা হয়েছে। আবার চেষ্টা করুন।",
};

export const isBn = () => state.lang === "bn";
export function tr(key, vars = {}) {
  const e = S[key];
  let s = e ? (isBn() && e[1] ? e[1] : e[0]) : key;
  if (typeof s === "string") for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, v);
  return s;
}
export const levelName = (k) => (S.levels[isBn() ? 1 : 0][k]) || k;
const PATTERNS = [
  [/^Tuition '(.+)' has an installment due on (\S+) \((\d+) day\(s\) left\)\. Verify payment details with your university's official finance office\.$/, (n, d, k) => `টিউশন '${n}'-এর একটি কিস্তির সময়সীমা ${d} (আর ${k} দিন বাকি)। পেমেন্টের তথ্য বিশ্ববিদ্যালয়ের অফিসিয়াল অর্থ বিভাগ থেকে যাচাই করুন।`],
  [/^Savings milestone: '(.+)' has reached (\d+)% of its target \(based on the savings you entered\)\.$/, (n, p) => `সঞ্চয়ের মাইলফলক: '${n}' লক্ষ্যের ${p}% ছুঁয়েছে (আপনার দেওয়া সঞ্চয়ের ভিত্তিতে)।`],
  [/^Time to review your budget '(.+)' \(last updated (\S+)\)\.$/, (n, d) => `আপনার বাজেট '${n}' পর্যালোচনার সময় হয়েছে (সর্বশেষ হালনাগাদ ${d})।`],
  [/^Wrong password\. (\d+) attempt\(s\) left\.$/, (k) => `পাসওয়ার্ড ভুল। আর ${k} বার চেষ্টা করা যাবে।`],
  [/^Wrong PIN\. (\d+) attempt\(s\) left\.$/, (k) => `PIN ভুল। আর ${k} বার চেষ্টা করা যাবে।`],
];
export function serverMsg(m) {
  if (!isBn() || typeof m !== "string") return m;
  if (SERVER[m]) return SERVER[m];
  for (const [re, f] of PATTERNS) { const x = m.match(re); if (x) return f(...x.slice(1)); }
  return m;
}

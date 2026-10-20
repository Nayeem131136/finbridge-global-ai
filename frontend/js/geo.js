// City used on the globe for each currency. Origin of every route is the sender's city (Dhaka for BDT).
export const CITIES = {
  BDT: { name: "Dhaka", lat: 23.81, lon: 90.41 },
  USD: { name: "New York", lat: 40.71, lon: -74.0 },
  GBP: { name: "London", lat: 51.51, lon: -0.13 },
  EUR: { name: "Berlin", lat: 52.52, lon: 13.4 },
  AUD: { name: "Sydney", lat: -33.87, lon: 151.21 },
  CAD: { name: "Toronto", lat: 43.65, lon: -79.38 },
  CNY: { name: "Shenzhen", lat: 22.54, lon: 114.06 },
  MYR: { name: "Kuala Lumpur", lat: 3.14, lon: 101.69 },
  SGD: { name: "Singapore", lat: 1.35, lon: 103.82 },
  JPY: { name: "Tokyo", lat: 35.68, lon: 139.69 },
  INR: { name: "Delhi", lat: 28.61, lon: 77.21 },
  AED: { name: "Dubai", lat: 25.2, lon: 55.27 },
};

// Country -> capital/main city for the globe. Keys are lower-case names and common aliases.
const C = (name, lat, lon, ccy, ...aliases) => ({ name, lat, lon, ccy, aliases });
const COUNTRY_LIST = [
  C("Bangladesh", 23.81, 90.41, "BDT", "bd", "dhaka"),
  C("United States", 38.9, -77.04, "USD", "usa", "us", "u.s.", "u.s.a.", "america", "united states of america", "new york"),
  C("United Kingdom", 51.51, -0.13, "GBP", "uk", "u.k.", "england", "britain", "great britain", "scotland", "wales", "london"),
  C("Germany", 52.52, 13.4, "EUR", "deutschland", "berlin"),
  C("France", 48.86, 2.35, "EUR", "paris"),
  C("Italy", 41.9, 12.5, "EUR", "rome"),
  C("Spain", 40.42, -3.7, "EUR", "madrid"),
  C("Netherlands", 52.37, 4.9, "EUR", "holland", "amsterdam"),
  C("Ireland", 53.35, -6.26, "EUR", "dublin"),
  C("Finland", 60.17, 24.94, "EUR", "helsinki"),
  C("Australia", -35.28, 149.13, "AUD", "au", "sydney", "melbourne", "canberra"),
  C("Canada", 45.42, -75.7, "CAD", "ca", "toronto", "ottawa", "vancouver"),
  C("China", 39.9, 116.4, "CNY", "cn", "prc", "beijing", "shenzhen", "shanghai"),
  C("Malaysia", 3.14, 101.69, "MYR", "my", "kuala lumpur"),
  C("Singapore", 1.35, 103.82, "SGD", "sg"),
  C("Japan", 35.68, 139.69, "JPY", "jp", "tokyo"),
  C("India", 28.61, 77.21, "INR", "in", "delhi", "new delhi"),
  C("United Arab Emirates", 25.2, 55.27, "AED", "uae", "dubai", "abu dhabi"),
];
const norm = (s) => String(s || "").trim().toLowerCase().replace(/\s+/g, " ");
const INDEX = new Map();
COUNTRY_LIST.forEach((c) => { INDEX.set(norm(c.name), c); c.aliases.forEach((a) => INDEX.set(norm(a), c)); });
export const COUNTRY_NAMES = COUNTRY_LIST.map((c) => c.name);

// Returns { name, lat, lon, ccy } or null when the country is not in our small map.
export function findCountry(text) {
  const c = INDEX.get(norm(text));
  return c ? { name: c.name, lat: c.lat, lon: c.lon, ccy: c.ccy } : null;
}

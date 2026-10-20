// FinBridge 3D globe: dotted Earth, route arcs with flowing money packets, event ripples.
// Pure three.js, no network access: land data and the library are bundled in this folder.
import * as THREE from "../vendor/three.min.js";
import { CITIES } from "./geo.js";

const TEAL = new THREE.Color(0x2de2b0), BLUE = new THREE.Color(0x4c8dff), AMBER = new THREE.Color(0xffb84d);
const RED = new THREE.Color(0xff5d6c), GOLD = new THREE.Color(0xffd76a), WHITE = new THREE.Color(0xdff7ff);
const KIND = { good: TEAL, info: BLUE, warn: AMBER, bad: RED };

const ll = (lat, lon, r = 1) => {
  const phi = ((90 - lat) * Math.PI) / 180, th = ((lon + 180) * Math.PI) / 180;
  return new THREE.Vector3(-r * Math.sin(phi) * Math.cos(th), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(th));
};
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const costColor = (t) => (t < 0.5 ? TEAL.clone().lerp(AMBER, t * 2) : AMBER.clone().lerp(RED, (t - 0.5) * 2));

const LAND_VS = /* glsl */ `
  uniform float uTime, uPR, uSize, uPT; uniform vec3 uPO, uPC, uBase;
  attribute float aSeed; varying float vA; varying vec3 vC;
  void main(){
    vec3 n = normalize(position);
    vec4 mv = modelViewMatrix * vec4(position * 1.003, 1.0);
    float facing = dot(normalize(normalMatrix * n), vec3(0.0, 0.0, 1.0));
    float tw = 0.78 + 0.22 * sin(uTime * 1.4 + aSeed * 6.2831);
    float ripple = 0.0;
    if (uPT >= 0.0) {
      float d = acos(clamp(dot(n, normalize(uPO)), -1.0, 1.0));
      float w = uPT * 1.7;
      ripple = exp(-pow((d - w) * 7.5, 2.0)) * (1.0 - smoothstep(0.0, 2.3, uPT));
    }
    vC = mix(uBase, uPC, clamp(ripple * 1.3, 0.0, 1.0));
    vA = (0.30 + 0.70 * smoothstep(-0.05, 0.85, facing)) * tw + ripple * 1.4;
    gl_PointSize = uSize * uPR * (1.0 + ripple * 1.6) * (3.3 / -mv.z);
    gl_Position = projectionMatrix * mv;
  }`;
const LAND_FS = /* glsl */ `
  varying float vA; varying vec3 vC;
  void main(){ float d = length(gl_PointCoord - 0.5); if (d > 0.5) discard;
    gl_FragColor = vec4(vC, smoothstep(0.5, 0.12, d) * clamp(vA, 0.0, 1.6)); }`;

const BASE_VS = /* glsl */ `varying vec3 vN, vV; void main(){ vN = normalize(normalMatrix * normal);
  vec4 mv = modelViewMatrix * vec4(position, 1.0); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }`;
const BASE_FS = /* glsl */ `varying vec3 vN, vV; void main(){ float f = pow(1.0 - max(dot(vN, vV), 0.0), 2.4);
  vec3 col = mix(vec3(0.018, 0.055, 0.105), vec3(0.03, 0.10, 0.17), 1.0 - f) + vec3(0.04, 0.30, 0.34) * f * 0.55;
  gl_FragColor = vec4(col, 1.0); }`;

const ATM_VS = /* glsl */ `varying vec3 vN; void main(){ vN = normalize(normalMatrix * normal);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const ATM_FS = /* glsl */ `uniform vec3 uColor; uniform float uK; varying vec3 vN; void main(){
  float i = pow(max(0.74 - dot(vN, vec3(0.0, 0.0, 1.0)), 0.0), 3.0); gl_FragColor = vec4(uColor, 1.0) * i * uK; }`;

const DOT_VS = /* glsl */ `uniform float uPR; attribute float aSize; attribute float aAlpha; varying float vAlpha;
  void main(){ vAlpha = aAlpha; vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = aSize * uPR * (3.3 / -mv.z); gl_Position = projectionMatrix * mv; }`;
const DOT_FS = /* glsl */ `uniform vec3 uColor; varying float vAlpha; void main(){
  float d = length(gl_PointCoord - 0.5); if (d > 0.5) discard;
  gl_FragColor = vec4(mix(uColor, vec3(1.0), smoothstep(0.25, 0.0, d) * 0.7), smoothstep(0.5, 0.0, d) * vAlpha); }`;

export class Globe {
  constructor(canvas, labelLayer, { reducedMotion = false } = {}) {
    this.canvas = canvas; this.labels = labelLayer; this.reduced = reducedMotion;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
    if (!this.renderer.getContext()) throw new Error("WebGL unavailable");
    this.renderer.setClearColor(0x000000, 0);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(38, 1, 0.1, 200);
    this.camZ = 3.4; this.camera.position.set(0, 0, this.camZ);
    this.world = new THREE.Group(); this.scene.add(this.world);
    this.time = 0; this.pr = 1; this.insets = { left: 0, right: 0, top: 0, bottom: 0 };
    this.vel = new THREE.Vector2(); this.dragging = false; this.idle = 0; this.autoRotate = true;
    this.focusAnim = null; this.route = null; this.pulseT = -1; this.shake = 0; this.atmK = 1; this.atmTarget = TEAL.clone();
    this.markers = []; this.coins = []; this.cityLabels = [];
    this._build(); this._bind();
  }

  async init() {
    const land = await (await fetch("data/land.json")).json();
    const pos = new Float32Array(land.length * 3), seed = new Float32Array(land.length);
    land.forEach(([lat, lon], i) => { const v = ll(lat, lon); pos.set([v.x, v.y, v.z], i * 3); seed[i] = Math.random(); });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3)); g.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));
    this.landMat = new THREE.ShaderMaterial({
      vertexShader: LAND_VS, fragmentShader: LAND_FS, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      uniforms: { uTime: { value: 0 }, uPR: { value: this.pr }, uSize: { value: 3.0 }, uPT: { value: -1 },
        uPO: { value: new THREE.Vector3(0, 1, 0) }, uPC: { value: TEAL.clone() }, uBase: { value: new THREE.Color(0x6fd3ff) } },
    });
    this.land = new THREE.Points(g, this.landMat); this.world.add(this.land);
    // opening: start turned away, then glide to Dhaka
    this.world.quaternion.copy(this._facing(ll(23.81, 90.41)).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), -1.6)));
    this.focusOn(ll(23.81, 90.41), 3.6, 2.4);
    this.last = performance.now(); requestAnimationFrame(this._tick);
    return this;
  }

  // ------------------------------------------------------------------ build
  _build() {
    const base = new THREE.Mesh(new THREE.SphereGeometry(0.996, 64, 64), new THREE.ShaderMaterial({ vertexShader: BASE_VS, fragmentShader: BASE_FS }));
    this.world.add(base);
    this.atm = new THREE.Mesh(new THREE.SphereGeometry(1.16, 64, 64), new THREE.ShaderMaterial({
      vertexShader: ATM_VS, fragmentShader: ATM_FS, side: THREE.BackSide, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false,
      uniforms: { uColor: { value: new THREE.Color(0x2fb7d6) }, uK: { value: 1.2 } } }));
    this.scene.add(this.atm);
    // graticule
    const pts = [];
    for (let lat = -60; lat <= 60; lat += 30) for (let lon = 0; lon < 360; lon += 4) pts.push(ll(lat, lon), ll(lat, lon + 4));
    for (let lon = -180; lon < 180; lon += 30) for (let lat = -88; lat < 88; lat += 4) pts.push(ll(lat, lon), ll(lat + 4, lon));
    this.world.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: 0x24517a, transparent: true, opacity: 0.22 })));
    // stars
    const sp = new Float32Array(900 * 3);
    for (let i = 0; i < 900; i++) { const v = new THREE.Vector3().randomDirection().multiplyScalar(18 + Math.random() * 22); sp.set([v.x, v.y, v.z], i * 3); }
    const sg = new THREE.BufferGeometry(); sg.setAttribute("position", new THREE.BufferAttribute(sp, 3));
    this.stars = new THREE.Points(sg, new THREE.PointsMaterial({ color: 0x9fc4ff, size: 1.3, sizeAttenuation: false, transparent: true, opacity: 0.55, depthWrite: false }));
    this.scene.add(this.stars);
  }

  _bind() {
    const c = this.canvas; let lx = 0, ly = 0;
    c.addEventListener("pointerdown", (e) => { this.dragging = true; lx = e.clientX; ly = e.clientY; this.idle = 0; this.focusAnim = null; c.setPointerCapture(e.pointerId); });
    c.addEventListener("pointermove", (e) => {
      if (!this.dragging) return;
      const dx = e.clientX - lx, dy = e.clientY - ly; lx = e.clientX; ly = e.clientY;
      this.vel.set(dx * 0.0042, dy * 0.0042); this._rotate(this.vel.x, this.vel.y);
    });
    const up = () => { this.dragging = false; };
    c.addEventListener("pointerup", up); c.addEventListener("pointercancel", up);
    c.addEventListener("wheel", (e) => { e.preventDefault(); this.camZ = THREE.MathUtils.clamp(this.camZ + e.deltaY * 0.0016, 2.2, 5.2); this._layout(); }, { passive: false });
    document.addEventListener("visibilitychange", () => { this.last = performance.now(); });
    this._ro = new ResizeObserver(() => this.resize()); this._ro.observe(c);
  }

  _rotate(dx, dy) {
    const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), dx).multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), dy));
    this.world.quaternion.premultiply(q);
  }

  setInsets(i) { this.insets = { ...this.insets, ...i }; this._layout(); }

  resize() {
    const w = this.canvas.clientWidth || 1, h = this.canvas.clientHeight || 1;
    this.pr = Math.min(window.devicePixelRatio || 1, 2);
    this.renderer.setPixelRatio(this.pr); this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
    if (this.landMat) this.landMat.uniforms.uPR.value = this.pr;
    this.W = w; this.H = h; this._layout();
  }

  _layout() {
    // shift the globe into the free area between the chat panel and the side HUD
    if (!this.W) return;
    this.camera.position.z = this.camZ;
    const visH = 2 * this.camZ * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2)), visW = visH * this.camera.aspect;
    const { left, right, top, bottom } = this.insets;
    const cx = (left + (this.W - right)) / 2 - this.W / 2, cy = (top + (this.H - bottom)) / 2 - this.H / 2;
    this.world.position.set((cx / this.W) * visW, (-cy / this.H) * visH, 0);
    const free = Math.min(this.W - left - right, this.H - top - bottom);
    const s = THREE.MathUtils.clamp(free * 0.42 / (this.H / visH), 0.25, 1.3);   // globe radius ~ 42% of the free area
    this.world.scale.setScalar(s); this.atm.scale.setScalar(s); this.atm.position.copy(this.world.position);
  }

  // ------------------------------------------------------------------ camera
  _facing(vLocal) { return new THREE.Quaternion().setFromUnitVectors(vLocal.clone().normalize(), new THREE.Vector3(0, 0, 1)); }

  focusOn(v, dur = 1.6, zoom = null) {
    if (this.reduced) { this.world.quaternion.copy(this._facing(v)); if (zoom) { this.camZ = zoom; this._layout(); } return; }
    this.focusAnim = { from: this.world.quaternion.clone(), to: this._facing(v), t: 0, dur, z0: this.camZ, z1: zoom ?? this.camZ };
  }

  // ------------------------------------------------------------------ routes
  clearRoute() {
    if (!this.route) return;
    this.route.objs.forEach((o) => { this.world.remove(o); o.traverse?.((n) => { n.geometry?.dispose(); n.material?.dispose?.(); }); });
    this.route.labels.forEach((l) => l.el.remove()); this.route = null;
    this.markers.length = 0;
  }

  // Home country -> study country: one neutral arc, no provider quotes. a and b are {name, lat, lon, ccy}.
  setCountryRoute(a, b) {
    if (!a || !b || (a.lat === b.lat && a.lon === b.lon)) return;
    this.setRoute(a.ccy, b.ccy, [{ provider: "", total_cost_pct: 0, speed_hours: 24 }], { a, b, neutral: true });
  }

  setRoute(fromCcy, toCcy, quotes = [], opts = {}) {
    const a = opts.a || CITIES[fromCcy] || CITIES.BDT, b = opts.b || CITIES[toCcy];
    if (!b || !quotes.length) return;
    this.clearRoute();
    const A = ll(a.lat, a.lon), B = ll(b.lat, b.lon), ang = A.angleTo(B);
    const objs = [], labels = [], arcs = [];
    const costs = quotes.map((q) => q.total_cost_pct), min = Math.min(...costs), max = Math.max(...costs);
    quotes.slice(0, 4).forEach((q, i) => {
      const t = max > min ? (q.total_cost_pct - min) / (max - min) : 0, col = costColor(t);
      const h = 0.14 + 0.2 * (ang / Math.PI) + i * 0.055, N = 64, pts = [];
      const s = Math.sin(ang) || 1e-6;
      for (let k = 0; k <= N; k++) {
        const u = k / N, p = A.clone().multiplyScalar(Math.sin((1 - u) * ang) / s).add(B.clone().multiplyScalar(Math.sin(u * ang) / s));
        pts.push(p.normalize().multiplyScalar(1 + h * Math.pow(Math.sin(Math.PI * u), 0.85)));
      }
      const curve = new THREE.CatmullRomCurve3(pts);
      const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 96, i === 0 ? 0.0042 : 0.0032, 6, false),
        new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: i === 0 ? 0.95 : 0.7, blending: THREE.AdditiveBlending, depthWrite: false }));
      const glow = new THREE.Mesh(new THREE.TubeGeometry(curve, 96, i === 0 ? 0.014 : 0.009, 8, false),
        new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: i === 0 ? 0.17 : 0.09, blending: THREE.AdditiveBlending, depthWrite: false }));
      const total = tube.geometry.index.count, gtotal = glow.geometry.index.count;
      tube.geometry.setDrawRange(0, this.reduced ? total : 0); glow.geometry.setDrawRange(0, this.reduced ? gtotal : 0);
      // flowing packets: faster arcs for faster providers
      const K = 24, pos = new Float32Array(K * 3), size = new Float32Array(K), alpha = new Float32Array(K);
      for (let k = 0; k < K; k++) { const trail = k % 8; size[k] = 11 - trail * 1.15; alpha[k] = (1 - trail / 8) * 0.95; }
      const pg = new THREE.BufferGeometry();
      pg.setAttribute("position", new THREE.BufferAttribute(pos, 3)); pg.setAttribute("aSize", new THREE.BufferAttribute(size, 1)); pg.setAttribute("aAlpha", new THREE.BufferAttribute(alpha, 1));
      const pm = new THREE.ShaderMaterial({ vertexShader: DOT_VS, fragmentShader: DOT_FS, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
        uniforms: { uPR: { value: this.pr }, uColor: { value: col } } });
      const packets = new THREE.Points(pg, pm); packets.frustumCulled = false; packets.visible = false;
      objs.push(tube, glow, packets);
      const el = document.createElement("div"); el.className = "rlabel" + (i === 0 ? " best" : "");
      const nm = document.createElement("b"); nm.textContent = q.provider.replace(/\s*\(.*\)/, "");
      const sub = document.createElement("span"); sub.textContent = `${q.total_cost_pct.toFixed(2)}% · ${q.speed_hours < 24 ? q.speed_hours + "h" : Math.round(q.speed_hours / 24) + "d"}`;
      el.append(nm, sub); el.style.setProperty("--c", "#" + col.getHexString());
      if (!opts.neutral) { this.labels.append(el); labels.push({ el, curve, u: 0.5 + (i % 2 ? 0.07 : -0.07) }); }
      arcs.push({ curve, tube, glow, total, gtotal, packets, speed: 0.08 + 0.5 * Math.exp(-q.speed_hours / 20), phase: i * 0.21, delay: i * 0.25, prog: 0, quote: q, name: q.provider });
    });
    [A, B].forEach((p, idx) => {
      const m = new THREE.Mesh(new THREE.RingGeometry(0.016, 0.022, 48), new THREE.MeshBasicMaterial({ color: idx ? WHITE : TEAL, transparent: true, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false }));
      m.position.copy(p).multiplyScalar(1.004); m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), p.clone().normalize());
      const d = new THREE.Mesh(new THREE.SphereGeometry(0.009, 16, 16), new THREE.MeshBasicMaterial({ color: idx ? WHITE : TEAL }));
      d.position.copy(p).multiplyScalar(1.004); objs.push(m, d); this.markers.push(m);
      const el = document.createElement("div"); el.className = "clabel"; el.textContent = (idx ? b : a).name; this.labels.append(el);
      labels.push({ el, point: p.clone().multiplyScalar(1.02), city: true });
    });
    objs.forEach((o) => this.world.add(o));
    this.route = { objs, labels, arcs, A, B, from: fromCcy, to: toCcy, t0: this.time };
    this.autoRotate = false;
    const mid = A.clone().add(B).normalize();
    this.focusOn(mid, 1.8, ang > 1.5 ? 4.2 : ang > 0.7 ? 3.5 : 2.9);
    this.pulse("info", fromCcy, a);
  }

  // ------------------------------------------------------------------ effects
  pulse(kind = "info", ccy = "BDT", city = null) {
    const c = city || CITIES[ccy] || CITIES.BDT;
    if (!this.landMat) return;
    const u = this.landMat.uniforms; u.uPO.value.copy(ll(c.lat, c.lon)); u.uPC.value.copy(KIND[kind] || BLUE); u.uPT.value = 0; this.pulseT = 0;
    this.atmTarget = (KIND[kind] || TEAL).clone(); this.atmHold = 1.4;
    if (kind === "bad" && !this.reduced) this.shake = 1;
  }

  // animate a coin along the arc of the chosen provider; resolves when it lands
  sendCoin(providerName) {
    return new Promise((resolve) => {
      const r = this.route; if (!r) return resolve();
      const arc = r.arcs.find((a) => providerName && a.name === providerName) || r.arcs[0];
      const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(3), 3));
      g.setAttribute("aSize", new THREE.BufferAttribute(new Float32Array([34]), 1)); g.setAttribute("aAlpha", new THREE.BufferAttribute(new Float32Array([1]), 1));
      const pts = new THREE.Points(g, new THREE.ShaderMaterial({ vertexShader: DOT_VS, fragmentShader: DOT_FS, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
        uniforms: { uPR: { value: this.pr }, uColor: { value: GOLD } } }));
      pts.frustumCulled = false; this.world.add(pts);
      this.coins.push({ pts, arc, t: 0, dur: this.reduced ? 0.01 : 1.9, done: () => { this.world.remove(pts); g.dispose(); this.pulse("good", r.to); resolve(); } });
    });
  }

  // ------------------------------------------------------------------ frame loop
  _tick = (now) => {
    requestAnimationFrame(this._tick);
    if (document.hidden) return;
    const dt = Math.min(0.05, (now - this.last) / 1000); this.last = now; this.time += dt;
    if (this.landMat) this.landMat.uniforms.uTime.value = this.time;
    // camera focus animation
    if (this.focusAnim) {
      const f = this.focusAnim; f.t += dt / f.dur; const k = ease(Math.min(f.t, 1));
      this.world.quaternion.slerpQuaternions(f.from, f.to, k);
      this.camZ = f.z0 + (f.z1 - f.z0) * k; this._layout();
      if (f.t >= 1) this.focusAnim = null;
    } else if (!this.dragging) {
      if (Math.abs(this.vel.x) + Math.abs(this.vel.y) > 1e-4) { this._rotate(this.vel.x, this.vel.y); this.vel.multiplyScalar(0.94); }
      else if (this.autoRotate && !this.reduced) { this.idle += dt; this._rotate(0.045 * dt, 0); }
    }
    // pulse + atmosphere tint
    if (this.pulseT >= 0) { this.pulseT += dt; this.landMat.uniforms.uPT.value = this.pulseT; if (this.pulseT > 2.4) { this.pulseT = -1; this.landMat.uniforms.uPT.value = -1; } }
    const am = this.atm.material.uniforms.uColor.value;
    if (this.atmHold > 0) { this.atmHold -= dt; am.lerp(this.atmTarget, 0.12); } else am.lerp(new THREE.Color(0x2fb7d6), 0.03);
    // shake
    if (this.shake > 0.01) { this.shake *= 0.9; this.camera.position.x = (Math.random() - 0.5) * 0.03 * this.shake; this.camera.position.y = (Math.random() - 0.5) * 0.03 * this.shake; }
    else { this.camera.position.x = 0; this.camera.position.y = 0; }
    this.stars.rotation.y += dt * 0.004;
    // markers breathe
    this.markers.forEach((m, i) => { const s = 1 + 0.55 * ((this.time * 0.9 + i * 0.5) % 1); m.scale.setScalar(s); m.material.opacity = 1 - ((this.time * 0.9 + i * 0.5) % 1); });
    // arcs: draw-in and packets
    if (this.route) {
      const r = this.route;
      r.arcs.forEach((a) => {
        const e = this.reduced ? 1 : Math.min(1, Math.max(0, (this.time - r.t0 - a.delay) / 1.3));
        if (a.prog < 1) { a.prog = e; const k = ease(e); const seg = 36, sg = 6 * 8;
          a.tube.geometry.setDrawRange(0, Math.floor((a.total * k) / 36) * 36); a.glow.geometry.setDrawRange(0, Math.floor((a.gtotal * k) / 48) * 48); }
        if (e >= 1) {
          a.packets.visible = true; const p = a.packets.geometry.attributes.position; const base = this.reduced ? 0.3 : (this.time * a.speed + a.phase);
          for (let k = 0; k < 24; k++) { const pk = Math.floor(k / 8), trail = k % 8; const u = (((base + pk / 3 - trail * 0.011) % 1) + 1) % 1; const v = a.curve.getPoint(u); p.setXYZ(k, v.x, v.y, v.z); }
          p.needsUpdate = true;
        }
      });
      this._placeLabels(r);
    }
    // coins
    for (let i = this.coins.length - 1; i >= 0; i--) {
      const c = this.coins[i]; c.t += dt / c.dur; const u = Math.min(1, ease(c.t)), v = c.arc.curve.getPoint(u);
      c.pts.geometry.attributes.position.setXYZ(0, v.x, v.y, v.z); c.pts.geometry.attributes.position.needsUpdate = true;
      if (c.t >= 1) { c.done(); this.coins.splice(i, 1); }
    }
    this.renderer.render(this.scene, this.camera);
  };

  _placeLabels(r) {
    const cam = this.camera, v = new THREE.Vector3(), nrm = new THREE.Vector3(), cp = cam.position;
    r.labels.forEach((l) => {
      v.copy(l.city ? l.point : l.curve.getPoint(l.u)); this.world.localToWorld(v);
      nrm.copy(v).sub(this.world.position).normalize();
      const facing = nrm.dot(cp.clone().sub(v).normalize());
      v.project(cam);
      const x = (v.x * 0.5 + 0.5) * this.W, y = (-v.y * 0.5 + 0.5) * this.H;
      l.el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) translate(-50%, ${l.city ? "-170%" : "-50%"})`;
      l.el.style.opacity = facing > 0.12 ? "1" : "0";
    });
  }
}

"""Profile countries drive the globe route (home -> study country); unknown country is ignored; no page errors."""
from playwright.sync_api import sync_playwright
errs=[]
with sync_playwright() as p:
    br=p.chromium.launch(args=["--use-gl=swiftshader","--enable-unsafe-swiftshader","--no-sandbox"]); pg=br.new_context(viewport={"width":1366,"height":820}).new_page()
    pg.on("pageerror",lambda e: errs.append(str(e)))
    pg.goto("http://localhost:8010"); pg.wait_for_selector(".authcard"); pg.click(".authcard >> text=Create account")
    pg.fill(".authcard form input[type=text]","Globe Tester"); pg.fill(".authcard form input[type=email]","globe@example.com")
    w=pg.locator(".authcard form input[type=password]"); w.nth(0).fill("Globepass1234"); w.nth(1).fill("Globepass1234"); pg.check("#terms"); pg.click(".authcard form button[type=submit]")
    pg.wait_for_selector("text=Welcome back")
    def labels(): return pg.eval_on_selector_all("#labels .clabel","els=>els.map(e=>e.textContent)")
    def open_profile(): pg.click("#acct button.pill"); pg.click("#acct .menu >> text=Profile")
    open_profile()
    pg.wait_for_selector("text=Your profile")
    d=pg.locator(".modal.dyn")
    d.get_by_label("Home country").fill("Bangladesh"); d.get_by_label("Study country").fill("UK"); d.locator("button.go",has_text="Save").click()
    pg.wait_for_timeout(3000); l=labels(); print("route labels (Bangladesh -> UK):", l);
    pg.screenshot(path="18_globe_bd_uk.png")
    open_profile(); pg.wait_for_selector("text=Your profile"); d=pg.locator(".modal.dyn")
    d.get_by_label("Study country").fill("Canada"); d.locator("button.go",has_text="Save").click(); pg.wait_for_timeout(2500); print("labels (Bangladesh -> Canada):", labels())
    open_profile(); pg.wait_for_selector("text=Your profile"); d=pg.locator(".modal.dyn")
    d.get_by_label("Study country").fill("Atlantis"); d.locator("button.go",has_text="Save").click(); pg.wait_for_timeout(1500); print("unknown country ok, labels:", labels())
    br.close()
print("ERRORS",errs)

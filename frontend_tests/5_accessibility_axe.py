import json
from playwright.sync_api import sync_playwright
AX=open("node_modules/axe-core/axe.min.js").read()
def run(pg,label):
    pg.evaluate(AX); r=pg.evaluate("axe.run(document,{runOnly:['wcag2a','wcag2aa','best-practice']}).then(r=>r.violations.map(v=>({id:v.id,impact:v.impact,n:v.nodes.length,ex:v.nodes[0].target.join(' ').slice(0,80)})))")
    print(label); [print("  ",v) for v in r]
with sync_playwright() as p:
    br=p.chromium.launch(args=["--use-gl=swiftshader","--enable-unsafe-swiftshader","--no-sandbox"]); pg=br.new_page(viewport={"width":1366,"height":820})
    pg.goto("http://localhost:8010"); pg.wait_for_selector(".authcard"); run(pg,"welcome")
    pg.click(".authcard >> text=Create account"); run(pg,"signup")
    pg.fill(".authcard form input[type=text]","Axe Tester"); pg.fill(".authcard form input[type=email]","axe@example.com")
    w=pg.locator(".authcard form input[type=password]"); w.nth(0).fill("Axepass12345"); w.nth(1).fill("Axepass12345"); pg.check("#terms"); pg.click(".authcard form button[type=submit]"); pg.wait_for_selector("text=Welcome back")
    run(pg,"home"); pg.click("#tabPlans"); pg.wait_for_timeout(500); run(pg,"plans")
    pg.click("#acct button.pill"); pg.click("#acct .menu >> text=Profile"); pg.wait_for_selector("text=Your profile"); pg.wait_for_timeout(500); run(pg,"profile")

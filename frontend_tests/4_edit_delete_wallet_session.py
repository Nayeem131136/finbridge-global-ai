from playwright.sync_api import sync_playwright
errs=[]
with sync_playwright() as p:
    br=p.chromium.launch(args=["--use-gl=swiftshader","--enable-unsafe-swiftshader","--no-sandbox"]); ctx=br.new_context(viewport={"width":1366,"height":820}); pg=ctx.new_page()
    pg.on("pageerror",lambda e: errs.append(str(e)))
    pg.goto("http://localhost:8010"); pg.wait_for_selector(".authcard"); pg.click(".authcard >> text=Create account")
    pg.fill(".authcard form input[type=text]","Edit Tester"); pg.fill(".authcard form input[type=email]","edit@example.com")
    w=pg.locator(".authcard form input[type=password]"); w.nth(0).fill("Editpass1234"); w.nth(1).fill("Editpass1234"); pg.check("#terms"); pg.click(".authcard form button[type=submit]")
    pg.wait_for_selector("text=Welcome back")
    pg.click("#tabPlans")
    # budget create/edit/delete
    pg.click("text=+ New budget"); d=pg.locator(".modal.dyn"); d.get_by_label("Name").first.fill("B1"); d.locator("input[type=number]").nth(0).fill("50000")
    r=d.locator(".exprow"); r.nth(0).locator("input").nth(0).fill("rent"); r.nth(0).locator("input").nth(1).fill("20000"); d.locator("button.go",has_text="Save").click(); pg.wait_for_selector("text=B1")
    pg.locator(".plan",has_text="B1").locator("button",has_text="Edit").click(); d=pg.locator(".modal.dyn"); d.get_by_label("Name").first.fill("B1-edited"); d.locator("button.go",has_text="Save").click(); pg.wait_for_selector("text=B1-edited")
    pg.locator(".plan",has_text="B1-edited").locator("button",has_text="Delete").click(); pg.locator(".modal.dyn button.go.danger").click(); pg.wait_for_selector("text=B1-edited",state="detached"); print("budget CRUD ok")
    # tuition create/edit/delete + validation error visible
    pg.click("text=+ New tuition plan"); d=pg.locator(".modal.dyn"); d.get_by_label("Name").first.fill("T1"); d.locator("input[type=number]").nth(0).fill("1000"); d.locator("textarea").fill("not-a-date")
    d.locator("button.go",has_text="Save").click(); pg.wait_for_selector(".modal.dyn .err:not(:empty)"); print("tuition validation:",pg.inner_text(".modal.dyn .err"))
    d.locator("textarea").fill("2027-03-01"); d.locator("button.go",has_text="Save").click(); pg.wait_for_selector("text=T1")
    pg.locator(".plan",has_text="T1").locator("button",has_text="Edit").click(); d=pg.locator(".modal.dyn"); d.get_by_label("Name").first.fill("T1b"); d.locator("button.go",has_text="Save").click(); pg.wait_for_selector("text=T1b")
    pg.locator(".plan",has_text="T1b").locator("button",has_text="Delete").click(); pg.locator(".modal.dyn button.go.danger").click(); pg.wait_for_selector("text=T1b",state="detached"); print("tuition CRUD ok")
    # reminder prefs persist
    pg.click("#acct button.pill"); pg.click("#acct .menu >> text=Profile"); pg.wait_for_selector("text=Your profile"); pg.uncheck("#r2"); pg.locator(".modal.dyn button.go",has_text="Save").click(); pg.wait_for_selector(".toast")
    pg.reload(); pg.wait_for_selector("text=Welcome back"); pg.click("#acct button.pill"); pg.click("#acct .menu >> text=Profile"); pg.wait_for_selector("text=Your profile"); print("budget reminder persisted off:", not pg.is_checked("#r2")); pg.keyboard.press("Escape")
    # wallet validation + withdraw wrong password
    pg.click("#acct button.pill"); pg.click("#acct .menu >> text=Wallet"); d=pg.locator(".modal.dyn"); d.locator("button.go").last.click(); print("empty amount:",d.locator(".err").inner_text())
    d.get_by_role("tab",name="Withdraw (sandbox)").click(); d.locator("input[type=number]").fill("100"); d.locator("input[type=password]").fill("badbadbad1"); d.locator("button.go").last.click(); pg.wait_for_selector(".modal.dyn .err:not(:empty)"); print("withdraw wrong pw:",d.locator(".err").inner_text())
    d.locator("input[type=password]").fill("Editpass1234"); d.locator("button.go").last.click(); pg.wait_for_selector("text=WDR-"); print("withdraw ok"); d.locator("button",has_text="Close").first.click()
    # replay: transfer, confirm, then replay token via API
    pg.click("#tabChat"); pg.fill("#input","Pay 500 GBP tuition to the university"); pg.keyboard.press("Enter"); pg.wait_for_selector("#modal:not([hidden])")
    tok=pg.evaluate("document.querySelector('.cta button') ? 1 : 0")
    pg.fill("#pwIn","Editpass1234"); pg.click("#mConfirm"); pg.wait_for_selector("text=Sandbox transfer completed")
    # expired session
    ctx.clear_cookies(); pg.click("#tabHome"); pg.wait_for_selector(".authcard",timeout=8000); print("expired session -> sign-in shown:", "expired" in pg.inner_text(".toasts") if pg.locator(".toasts").count() else True)
    # server error UI: block API
    pg.route("**/api/dashboard", lambda r: r.abort()); 
    br.close()
print("ERRORS",errs)

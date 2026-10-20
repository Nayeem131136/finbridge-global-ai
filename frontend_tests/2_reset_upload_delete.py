import re,time
from playwright.sync_api import sync_playwright
B="http://localhost:8010"; errs=[]
with sync_playwright() as p:
    br=p.chromium.launch(args=["--use-gl=swiftshader","--enable-unsafe-swiftshader","--no-sandbox"])
    pg=br.new_page(viewport={"width":1366,"height":820})
    pg.on("pageerror",lambda e: errs.append(str(e)))
    pg.goto(B); pg.wait_for_selector(".authcard")
    # validation messages
    pg.click(".authcard >> text=Create account"); pg.click(".authcard form button[type=submit]"); print("val1:",pg.inner_text(".authcard .err"))
    pg.fill(".authcard form input[type=text]","Reset User"); pg.fill(".authcard form input[type=email]","reset@example.com")
    pw=pg.locator(".authcard form input[type=password]"); pw.nth(0).fill("short"); pw.nth(1).fill("short"); pg.click(".authcard form button[type=submit]"); print("val2:",pg.inner_text(".authcard .err"))
    pw.nth(0).fill("Oldpass1234"); pw.nth(1).fill("Oldpass1234"); pg.check("#terms"); pg.click(".authcard form button[type=submit]")
    pg.wait_for_selector("text=Welcome back")
    # university other + invoice upload
    pg.click("#acct button.pill"); pg.click("#acct .menu >> text=Profile"); pg.wait_for_selector("text=Your profile")
    d=pg.locator(".modal.dyn"); d.locator(".uni.other").click(); d.get_by_placeholder("University name (if not listed)").fill("Tiny College of Arts")
    d.locator("button.go",has_text="Save").click(); pg.wait_for_selector("text=Tiny College of Arts")
    pg.click("#paneHome >> text=Check an invoice"); d=pg.locator(".modal.dyn"); d.locator("input[type=file]").set_input_files("inv.pdf"); d.locator("button.go",has_text="Check invoice").click()
    pg.wait_for_selector(".verdict",timeout=10000); print("verdict:",pg.inner_text(".verdict")); print("note:", "not proof" in pg.inner_text("#log"))
    pg.screenshot(path="11_invoice.png")
    # sign out, forgot password
    pg.click("#acct button.pill"); pg.click("#acct .menu >> text=Sign out"); pg.wait_for_selector(".authcard")
    pg.click(".authcard button.go >> text=Sign in"); pg.click(".authcard >> text=Forgot password?"); pg.fill(".authcard input[type=email]","reset@example.com"); pg.click(".authcard form button[type=submit]")
    pg.wait_for_selector(".note.good:not([hidden])"); print("forgot:",pg.inner_text(".authcard .note.good"))
    time.sleep(0.5)
    tok=re.findall(r"#reset=([A-Za-z0-9_\-]+)",open(__import__("os").environ.get("SERVER_LOG","server.log"),errors="ignore").read())[-1]
    pg.goto(B+"/#reset="+tok); pg.reload(); pg.wait_for_selector("text=Choose a new password")
    pw=pg.locator(".authcard form input[type=password]"); pw.nth(0).fill("Newpass5678"); pw.nth(1).fill("Newpass5678"); pg.click(".authcard form button[type=submit]")
    pg.wait_for_selector(".authcard h1:has-text('Sign in')")
    pg.fill(".authcard input[type=email]","reset@example.com"); pg.fill(".authcard input[type=password]","Oldpass1234"); pg.click(".authcard form button[type=submit]"); print("old pw:",pg.inner_text(".authcard .err"))
    pg.fill(".authcard input[type=password]","Newpass5678"); pg.click(".authcard form button[type=submit]"); pg.wait_for_selector("text=Welcome back")
    # delete account
    pg.click("#acct button.pill"); pg.click("#acct .menu >> text=Profile"); pg.wait_for_selector("text=Your profile")
    pg.click(".modal.dyn >> text=Delete my account and data"); d=pg.locator(".modal.dyn").last; d.locator("input[type=password]").fill("Newpass5678"); d.locator("button.go.danger").click()
    pg.wait_for_selector(".authcard"); print("deleted ok")
    br.close()
print("ERRORS",errs)

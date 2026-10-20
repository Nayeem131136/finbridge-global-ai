from playwright.sync_api import sync_playwright
errs=[]
with sync_playwright() as p:
    br=p.chromium.launch(args=["--use-gl=swiftshader","--enable-unsafe-swiftshader","--no-sandbox"]); ctx=br.new_context(viewport={"width":1366,"height":820}); pg=ctx.new_page()
    pg.on("pageerror",lambda e: errs.append(str(e)))
    pg.goto("http://localhost:8010"); pg.wait_for_selector(".authcard"); pg.click(".authcard >> text=Create account")
    pg.fill(".authcard form input[type=text]","Study Tester"); pg.fill(".authcard form input[type=email]","study@example.com")
    w=pg.locator(".authcard form input[type=password]"); w.nth(0).fill("Studypass1234"); w.nth(1).fill("Studypass1234"); pg.check("#terms"); pg.click(".authcard form button[type=submit]")
    pg.wait_for_selector("text=Welcome back"); pg.click("#tabStudy"); pg.wait_for_selector("text=No study plan yet")
    def new_plan(name, ccy, tuition, living, conf=0, pot=0):
        pg.click("text=+ New study plan"); d=pg.locator(".modal.dyn"); d.get_by_label("Name").first.fill(name)
        d.locator("select").first.select_option(ccy); d.get_by_label("Duration (years)").fill("2"); d.get_by_label("Tuition per year").fill(str(tuition)); d.get_by_label("Living cost per month").fill(str(living))
        d.get_by_label("Confirmed funding (family, loan, confirmed scholarship)").fill(str(conf)); d.get_by_label("Potential scholarships (NOT confirmed)").fill(str(pot))
        d.get_by_label("Target date (start of study)").fill("2027-09-01"); d.locator("button.go",has_text="Save").click(); pg.wait_for_selector(f".dcard.plan >> text={name}")
    # validation error visible
    pg.click("text=+ New study plan"); d=pg.locator(".modal.dyn"); d.get_by_label("Name").first.fill("Bad"); d.locator("button.go",has_text="Save").click(); pg.wait_for_selector(".modal.dyn .err:not(:empty)"); print("validation:",d.locator(".err").inner_text()); d.locator("button",has_text="Cancel").click()
    new_plan("UK Master","GBP",20000,1000,10000,8000); new_plan("AU Master","AUD",30000,1500); new_plan("US Master","USD",40000,1800)
    pg.screenshot(path="13_study_list.png")
    pg.locator(".dcard.plan",has_text="UK Master").locator("button",has_text="Open").click(); pg.wait_for_selector("text=What-if lab")
    pg.screenshot(path="14_study_detail.png",full_page=True)
    print("total shown:", pg.locator(".dcard >> text=Total estimated cost").count()>0, "| 64,000.00 GBP" , "64,000.00 GBP" in pg.inner_text("#paneStudy"))
    pg.get_by_label("Tuition change %").fill("10"); pg.click("text=Calculate scenario"); pg.wait_for_selector(".wiout .stat"); print("whatif:",pg.inner_text(".wiout")[:140].replace("\n"," "))
    # quote
    pg.get_by_label("Provider (your label)").fill("Bank A website"); pg.get_by_label("Amount to send").fill("100000"); pg.get_by_label("Rate (receive per 1 sent)").fill("0.0062"); pg.get_by_label("Fee %").fill("1"); pg.click("text=Add quote"); pg.wait_for_selector("text=Entered by you"); print("quote ok")
    bt=pg.inner_text("#paneStudy"); print("rate board: as-of", "Rate as of" in bt, "| market", "Market rate" in bt, "| vs market", ("below market" in bt) or ("above market" in bt))
    assert "Rate as of" in bt and "Market rate" in bt
    # checklist toggle + add
    pg.locator(".ck input[type=checkbox]").first.check(); pg.get_by_label("New checklist item").fill("Book IELTS"); pg.keyboard.press("Enter"); pg.wait_for_selector("text=Book IELTS")
    # pdf download
    with pg.expect_download() as dl: pg.click("text=PDF report")
    path=dl.value.path(); print("pdf magic:", open(path,"rb").read(5))
    pg.click("text=← Back"); pg.wait_for_selector("text=+ New study plan")
    # compare
    for n in ("UK Master","AU Master","US Master"): pg.locator(".dcard.plan",has_text=n).locator("input[type=checkbox]").check()
    pg.click("text=Compare selected"); pg.wait_for_selector("text=Plan comparison"); pg.screenshot(path="15_study_compare.png"); print("compare ok")
    pg.click("text=← Back"); pg.click("text=Scholarship directory"); pg.wait_for_selector("text=Chevening"); print("scholarships ok"); pg.keyboard.press("Escape")
    # AI explain (rule engine)
    pg.click("#tabChat"); pg.fill("#input","Explain my study plan"); pg.keyboard.press("Enter"); pg.wait_for_selector(".msg.bot .card >> text=Study plan:",timeout=8000); print("ai tool card ok")
    # Bangla + mobile
    pg.click("#langBtn"); pg.click("#tabStudy"); pg.wait_for_timeout(800); pg.screenshot(path="16_study_bn.png")
    pg.set_viewport_size({"width":390,"height":780}); pg.wait_for_timeout(500); print("hscroll:",pg.evaluate("document.documentElement.scrollWidth>innerWidth")); pg.screenshot(path="17_study_mobile.png")
    br.close()
print("ERRORS",errs)

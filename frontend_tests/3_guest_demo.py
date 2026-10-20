from playwright.sync_api import sync_playwright
errs=[]
with sync_playwright() as p:
    br=p.chromium.launch(args=["--use-gl=swiftshader","--enable-unsafe-swiftshader","--no-sandbox"]); pg=br.new_page(viewport={"width":1366,"height":820})
    pg.on("pageerror",lambda e: errs.append(str(e)))
    pg.goto("http://localhost:8010"); pg.wait_for_selector(".authcard"); pg.click(".authcard >> text=Continue as demo guest")
    pg.click("#demoBtn"); pg.wait_for_selector("text=Sandbox transfer completed",timeout=60000); pg.wait_for_selector("text=Tamper",timeout=5000)
    pg.wait_for_selector("#tamperOut .st.ok",timeout=30000); print("demo ok", pg.inner_text("#tamperOut")[:120])
    pg.click("#tabExplore"); pg.wait_for_selector("#exResult .exrow2"); pg.click("#exSave"); pg.wait_for_selector(".toast"); print("guest save:",pg.inner_text(".toast"))
    br.close()
print(errs)

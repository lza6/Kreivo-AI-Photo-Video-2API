import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={"width":1280,"height":900})
        errs=[]; pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
        await pg.goto("http://127.0.0.1:8977/", wait_until="networkidle"); await pg.wait_for_timeout(2000)
        await pg.set_input_files("#file","test_1024.jpg")
        for svc in ["enhance","segment"]:
            await pg.select_option("#svc", svc)
            await pg.click("#btnSvc")
            if svc=="enhance":
                await pg.wait_for_selector("#out img", timeout=240000)
                print("enhance img:", (await pg.get_attribute("#out img","src"))[:90])
            else:
                await pg.wait_for_selector("#out pre", timeout=240000); await pg.wait_for_timeout(1500)
                txt=await pg.inner_text("#out"); print("segment out head:", txt[:140].replace("\n"," "))
        await pg.screenshot(path="shot_service.png", full_page=True)
        print("console errors:", errs[:3]); await b.close()
asyncio.run(main())

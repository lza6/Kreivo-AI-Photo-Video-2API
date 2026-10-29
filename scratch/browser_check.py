import asyncio, json, base64, pathlib
from playwright.async_api import async_playwright

URL="http://127.0.0.1:8977/"
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        pg=await b.new_page(viewport={"width":1280,"height":900})
        errs=[]; pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
        await pg.goto(URL, wait_until="networkidle")
        await pg.wait_for_timeout(2500)
        print("title:", await pg.title())
        print("health chip:", await pg.inner_text("#health"))
        print("style thumbs:", await pg.locator("#styles img").count())
        await pg.screenshot(path="shot_initial.png", full_page=True)

        # 文生图（最快路径，真实点击）
        await pg.fill("#prompt","a serene fantasy castle at sunset, oil painting")
        await pg.click("#btnT2I")
        await pg.wait_for_selector("#out img", timeout=180000)
        src=await pg.get_attribute("#out img","src")
        print("t2i img:", src[:100])
        print("t2i meta:", (await pg.inner_text("#out")).split("\n")[0])
        await pg.screenshot(path="shot_t2i.png", full_page=True)

        # 图生图（上传真实文件）
        await pg.set_input_files("#file","samples/input.jpg")
        await pg.fill("#prompt","make it a soft watercolor painting")
        await pg.click("#btnEdit")
        await pg.wait_for_selector("#out img", timeout=240000)
        print("i2i img:", (await pg.get_attribute("#out img","src"))[:100])
        await pg.screenshot(path="shot_i2i.png", full_page=True)

        # 图生视频
        await pg.click("#btnVideo")
        await pg.wait_for_selector("#out video", timeout=600000)
        vsrc=await pg.get_attribute("#out video","src")
        print("i2v video:", vsrc[:120])
        await pg.wait_for_timeout(2000)
        await pg.screenshot(path="shot_i2v.png", full_page=True)
        print("console errors:", errs[:5])
        await b.close()
asyncio.run(main())

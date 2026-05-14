"""生成最终交付文件：V18完整版 + V18脱敏版，各含自包含HTML和高清长图"""
import asyncio
import os

def main():
    # 读取 ECharts JS
    with open("data/echarts.min.js", "r") as f:
        echarts_js = f.read()

    # === V18 完整版 ===
    with open("data/产品经理_深度分析_v18.html", "r") as f:
        v18_html = f.read()
    v18_self = v18_html.replace(
        '<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>',
        f"<script>{echarts_js}</script>"
    )
    path_v18_html = "data/V18_完整版.html"
    with open(path_v18_html, "w", encoding="utf-8") as f:
        f.write(v18_self)
    size = os.path.getsize(path_v18_html) / 1024 / 1024
    print(f"✅ V18_完整版.html ({size:.1f}MB)")

    # === V18 脱敏版 ===
    with open("data/产品经理_深度分析_公开版.html", "r") as f:
        public_html = f.read()
    public_self = public_html.replace(
        '<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>',
        f"<script>{echarts_js}</script>"
    )
    path_pub_html = "data/V18_脱敏版.html"
    with open(path_pub_html, "w", encoding="utf-8") as f:
        f.write(public_self)
    size = os.path.getsize(path_pub_html) / 1024 / 1024
    print(f"✅ V18_脱敏版.html ({size:.1f}MB)")

    # === 高清长图 ===
    asyncio.run(gen_images(path_v18_html, path_pub_html))


async def gen_images(v18_path, pub_path):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # V18 完整版
        page = await browser.new_page(viewport={"width": 1200, "height": 800}, device_scale_factor=2)
        await page.goto(f"file://{os.path.abspath(v18_path)}")
        await page.wait_for_timeout(4000)
        png_path = "data/V18_完整版.png"
        await page.screenshot(path=png_path, full_page=True)
        size = os.path.getsize(png_path) / 1024 / 1024
        print(f"✅ V18_完整版.png ({size:.1f}MB, 2x Retina)")
        await page.close()

        # V18 脱敏版
        page = await browser.new_page(viewport={"width": 1200, "height": 800}, device_scale_factor=2)
        await page.goto(f"file://{os.path.abspath(pub_path)}")
        await page.wait_for_timeout(4000)
        png_path = "data/V18_脱敏版.png"
        await page.screenshot(path=png_path, full_page=True)
        size = os.path.getsize(png_path) / 1024 / 1024
        print(f"✅ V18_脱敏版.png ({size:.1f}MB, 2x Retina)")
        await page.close()

        await browser.close()


if __name__ == "__main__":
    main()
    print("\n🎉 全部完成！共4个文件：")
    print("   data/V18_完整版.html  — 自包含HTML，离线可用")
    print("   data/V18_完整版.png   — 高清长图")
    print("   data/V18_脱敏版.html  — 脱敏自包含HTML，可公开分享")
    print("   data/V18_脱敏版.png   — 脱敏高清长图，可公开分享")

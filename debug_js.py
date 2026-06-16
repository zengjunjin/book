"""
调试脚本 - 检查 JavaScript 错误
"""
from playwright.sync_api import sync_playwright


def debug_js_errors():
    print("="*60)
    print("🔍 调试 JavaScript 错误")
    print("="*60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1400, 'height': 900})
        page = context.new_page()

        # 捕获所有控制台消息
        console_messages = []
        page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))

        # 捕获页面错误
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # 捕获请求失败
        failed_requests = []
        page.on("requestfailed", lambda req: failed_requests.append(f"{req.method} {req.url}: {req.failure}"))

        print("\n1. 导航到登录页...")
        response = page.goto("http://localhost:5000/#/login", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(3000)

        print(f"  状态码: {response.status if response else 'None'}")
        print(f"  URL: {page.url}")

        # 检查页面标题
        print(f"\n2. 页面标题: {page.title()}")

        # 输出所有控制台消息
        if console_messages:
            print(f"\n3. 控制台消息 ({len(console_messages)}):")
            for msg in console_messages[:10]:
                print(f"  {msg[:100]}")
        else:
            print("\n3. 无控制台消息")

        # 输出页面错误
        if page_errors:
            print(f"\n4. 页面错误 ({len(page_errors)}):")
            for err in page_errors:
                print(f"  {err[:150]}")
        else:
            print("\n4. 无页面错误")

        # 输出失败的请求
        if failed_requests:
            print(f"\n5. 失败的请求 ({len(failed_requests)}):")
            for req in failed_requests[:5]:
                print(f"  {req}")
        else:
            print("\n5. 无失败请求")

        # 截图
        page.screenshot(path="/tmp/debug_js_error.png", full_page=True)
        print("\n  截图: /tmp/debug_js_error.png")

        # 打印当前 URL 和 hash
        print(f"\n6. 当前状态:")
        print(f"  URL: {page.url}")
        print(f"  Hash: {page.evaluate('() => window.location.hash')}")

        # 检查 Vue 是否正确挂载
        vue_mounted = page.evaluate("""
            () => {
                const app = document.querySelector('#app');
                return app ? app.innerHTML.length : 0;
            }
        """)
        print(f"  #app 内容长度: {vue_mounted}")

        browser.close()


if __name__ == "__main__":
    debug_js_errors()

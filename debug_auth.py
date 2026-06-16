"""
调试脚本 - 检查登录状态和路由问题
"""
from playwright.sync_api import sync_playwright


def debug_auth_and_routing():
    print("="*60)
    print("🔍 调试登录状态和路由")
    print("="*60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # 创建两个 context：一个干净，一个带 localStorage
        print("\n1. 测试新浏览器（无登录状态）...")
        context1 = browser.new_context()
        page1 = context1.new_page()

        page1.goto("http://localhost:5000/#/login", wait_until="networkidle", timeout=20000)
        page1.wait_for_timeout(3000)

        print(f"  URL: {page1.url}")
        content1 = page1.content()
        has_login_form1 = '用户名' in content1 or 'password' in content1.lower() or 'login' in content1.lower()
        print(f"  包含登录表单: {has_login_form1}")

        # 检查 localStorage
        local_storage1 = page1.evaluate("() => localStorage.getItem('token')")
        print(f"  localStorage.token: {local_storage1}")

        # 截图
        page1.screenshot(path="/tmp/debug_auth_01_fresh.png", full_page=True)
        print("  截图: /tmp/debug_auth_01_fresh.png")

        # 尝试手动导航到登录页
        print("\n2. 直接访问 /login...")
        page1.goto("http://localhost:5000/login", wait_until="networkidle", timeout=20000)
        page1.wait_for_timeout(2000)
        print(f"  URL: {page1.url}")
        page1.screenshot(path="/tmp/debug_auth_02_direct.png", full_page=True)

        # 测试已登录情况
        print("\n3. 测试带登录状态的浏览器...")
        context2 = browser.new_context()
        page2 = context2.new_page()

        # 设置一个假的 token
        page2.goto("http://localhost:5000", wait_until="networkidle", timeout=20000)
        page2.wait_for_timeout(1000)
        page2.evaluate("() => localStorage.setItem('token', 'fake_token_for_test')")
        page2.evaluate("() => localStorage.setItem('user', JSON.stringify({id: 8, username: \"user8\"}))")

        page2.goto("http://localhost:5000/#/login", wait_until="networkidle", timeout=20000)
        page2.wait_for_timeout(2000)

        print(f"  URL: {page2.url}")
        page2.screenshot(path="/tmp/debug_auth_03_loggedin.png", full_page=True)

        # 检查路由守卫
        print("\n4. 检查 Vue Router 配置...")

        # 获取路由信息
        router_info = page1.evaluate("""
            () => {
                if (window.__VUE_DEVTOOLS_GLOBAL_HOOK__) {
                    return 'Vue DevTools detected';
                }
                return 'No Vue DevTools';
            }
        """)
        print(f"  {router_info}")

        # 获取实际 DOM 结构
        print("\n5. 详细 DOM 检查...")
        all_links = page1.locator('a, .router-link, [href]').all()
        print(f"  链接/路由元素: {len(all_links)} 个")
        for i, link in enumerate(all_links[:10]):
            href = link.get_attribute('href') or ''
            text = link.inner_text()[:30]
            print(f"    [{i}] href={href}, text={text}")

        # 检查是否有导航到登录的链接
        print("\n6. 查找登录相关元素...")
        login_elements = page1.locator('*:has-text("登录"), *:has-text("login"), *:has-text("Login")').all()
        print(f"  包含'登录'的元素: {len(login_elements)} 个")

        browser.close()


if __name__ == "__main__":
    debug_auth_and_routing()

"""
调试脚本 - 检查登录页面 DOM 结构
"""
from playwright.sync_api import sync_playwright


def debug_login_page():
    print("="*60)
    print("🔍 调试登录页面 DOM 结构")
    print("="*60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1400, 'height': 900})
        page = context.new_page()

        # 捕获控制台消息
        def log_console(msg):
            print(f"[CONSOLE {msg.type}] {msg.text[:100]}")
        page.on("console", log_console)

        # 导航到登录页
        print("\n1. 导航到登录页...")
        page.goto("http://localhost:5000/#/login", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(3000)

        # 截图
        page.screenshot(path="/tmp/debug_login_01.png", full_page=True)
        print("  截图: /tmp/debug_login_01.png")

        # 获取页面内容
        content = page.content()
        print(f"\n2. 页面内容长度: {len(content)} 字符")

        # 检查关键元素
        print("\n3. 检查 DOM 元素:")

        # 检查所有 input
        inputs = page.locator('input').all()
        print(f"  - input 元素: {len(inputs)} 个")
        for i, inp in enumerate(inputs[:5]):
            placeholder = inp.get_attribute('placeholder') or ''
            inp_type = inp.get_attribute('type') or 'text'
            print(f"    [{i}] type={inp_type}, placeholder={placeholder}")

        # 检查 el-input
        el_inputs = page.locator('.el-input').all()
        print(f"  - .el-input 元素: {len(el_inputs)} 个")

        # 检查内部 input
        el_input_inners = page.locator('.el-input__inner').all()
        print(f"  - .el-input__inner 元素: {len(el_input_inners)} 个")
        for i, inp in enumerate(el_input_inners[:5]):
            placeholder = inp.get_attribute('placeholder') or ''
            print(f"    [{i}] placeholder={placeholder}")

        # 检查 button
        buttons = page.locator('button').all()
        print(f"  - button 元素: {len(buttons)} 个")
        for i, btn in enumerate(buttons[:5]):
            text = btn.inner_text()[:30]
            print(f"    [{i}] text={text}")

        # 检查 el-button
        el_buttons = page.locator('.el-button').all()
        print(f"  - .el-button 元素: {len(el_buttons)} 个")

        # 尝试不同的选择器
        print("\n4. 尝试不同的选择器:")

        selectors = [
            'input[placeholder="用户名"]',
            'input[placeholder="密码"]',
            '.el-input input',
            '.el-input__inner',
            'input[type="text"]',
            'input[type="password"]',
            'form input',
            '.login-form input',
        ]

        for sel in selectors:
            count = page.locator(sel).count()
            print(f"  - '{sel}': {count} 个")

        # 输出页面文本
        print("\n5. 页面可见文本:")
        visible_text = page.inner_text('body')[:500]
        print(f"  {visible_text}...")

        # 最终截图
        page.screenshot(path="/tmp/debug_login_02.png", full_page=True)
        print("\n  最终截图: /tmp/debug_login_02.png")

        browser.close()


if __name__ == "__main__":
    debug_login_page()

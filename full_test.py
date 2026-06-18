from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    # ===== 测试1: 注册页面加载 =====
    print("=" * 60)
    print("测试1: 访问注册页面")
    page.goto("http://localhost:5173/#/register")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    print(f"  当前URL: {page.url}")
    print(f"  控制台错误数: {len(console_errors)}")
    console_errors.clear()

    # ===== 测试2: 填写注册表单 =====
    print("=" * 60)
    print("测试2: 填写注册表单")
    timestamp = int(time.time())
    test_username = f"bookuser_{timestamp}"
    test_password = "TestPass123"

    page.fill('input[placeholder*="用户名"]', test_username)
    page.fill('input[placeholder*="邮箱"]', f"{test_username}@test.com")
    page.fill('input[placeholder="密码"]', test_password)
    page.fill('input[placeholder="确认密码"]', test_password)
    page.wait_for_timeout(500)
    print(f"  用户名: {test_username}")
    print(f"  密码: {test_password}")

    # 检查提交按钮状态
    submit_btn = page.locator('button:has-text("注册")')
    is_disabled = submit_btn.is_disabled()
    print(f"  提交按钮禁用: {is_disabled}")

    # ===== 测试3: 点击注册 =====
    print("=" * 60)
    print("测试3: 点击注册")
    if not is_disabled:
        submit_btn.click()
        page.wait_for_timeout(3000)
        print(f"  当前URL: {page.url}")
        print(f"  控制台错误数: {len(console_errors)}")
        for err in console_errors:
            print(f"    ERROR: {err}")
        console_errors.clear()

        # 检查是否跳转到登录页
        if "/login" in page.url:
            print("  ✅ 注册成功，已跳转到登录页")

            # ===== 测试4: 使用新账号登录 =====
            print("=" * 60)
            print("测试4: 使用新账号登录")
            page.fill('input[placeholder*="用户名"]', test_username)
            page.fill('input[placeholder="密码"]', test_password)
            page.wait_for_timeout(500)

            login_btn = page.locator('button:has-text("登录")')
            login_btn.click()
            page.wait_for_timeout(3000)
            print(f"  当前URL: {page.url}")
            print(f"  控制台错误数: {len(console_errors)}")
            for err in console_errors:
                print(f"    ERROR: {err}")
            console_errors.clear()

            if "/" == page.url or "/home" in page.url or page.url.endswith("/"):
                print("  ✅ 登录成功，已跳转到首页")
            else:
                print(f"  ⚠️ 登录后URL: {page.url}")

        else:
            print("  ❌ 注册未成功跳转")
            # 检查页面上的错误信息
            error_el = page.locator(".el-message--error").first
            if error_el.count() > 0:
                print(f"  错误信息: {error_el.text_content()}")
    else:
        print("  ❌ 提交按钮被禁用，无法提交！")

    # ===== 测试5: 不填邮箱注册 =====
    print("=" * 60)
    print("测试5: 不填邮箱注册（邮箱可选测试）")
    page.goto("http://localhost:5173/#/register")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    timestamp2 = int(time.time())
    test_username2 = f"bookuser2_{timestamp2}"
    page.fill('input[placeholder*="用户名"]', test_username2)
    # 故意不填邮箱
    page.fill('input[placeholder="密码"]', "TestPass456")
    page.fill('input[placeholder="确认密码"]', "TestPass456")
    page.wait_for_timeout(500)

    submit_btn2 = page.locator('button:has-text("注册")')
    is_disabled2 = submit_btn2.is_disabled()
    print(f"  不填邮箱 - 提交按钮禁用: {is_disabled2}")
    if not is_disabled2:
        submit_btn2.click()
        page.wait_for_timeout(3000)
        print(f"  当前URL: {page.url}")
        if "/login" in page.url:
            print("  ✅ 不填邮箱也能注册成功")
        else:
            error_el = page.locator(".el-message--error").first
            if error_el.count() > 0:
                print(f"  ❌ 注册失败: {error_el.text_content()}")
            else:
                print(f"  ⚠️ 状态未知，URL: {page.url}")
    else:
        print("  ❌ 提交按钮被禁用（邮箱必填）")

    browser.close()
    print("=" * 60)
    print("测试完成！")

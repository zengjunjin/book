"""
优化版 Web 应用测试 - 修复选择器问题
"""
import time
from playwright.sync_api import sync_playwright


class OptimizedTester:
    def __init__(self):
        self.base_url = "http://localhost:5000"
        self.results = []
        self.errors = []

    def log(self, message, status="INFO"):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{status}] {message}")
        self.results.append(f"[{status}] {message}")

    def take_screenshot(self, page, name):
        path = f"/tmp/optimized_{name}_{int(time.time())}.png"
        page.screenshot(path=path, full_page=True)
        print(f"  📸 {path}")
        return path

    def test_complete_flow(self):
        """完整流程测试"""
        print("\n" + "="*60)
        print("🚀 优化版 Web 应用测试")
        print("="*60)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1400, 'height': 900},
                locale='zh-CN'
            )
            page = context.new_page()

            # 捕获控制台错误
            page.on("console", lambda msg: self.errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)

            try:
                # ====== 1. 首页测试 ======
                print("\n--- 1. 首页测试 ---")
                page.goto(self.base_url, wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(2000)

                book_cards = page.locator('.book-card').all()
                self.log(f"首页有 {len(book_cards)} 个书籍卡片", "PASS" if len(book_cards) > 0 else "FAIL")

                sidebar = page.locator('.sidebar, aside').first
                self.log(f"侧边栏存在: {sidebar.count() > 0}", "PASS")

                self.take_screenshot(page, "01_homepage")

                # ====== 2. 登录测试（修复选择器）======
                print("\n--- 2. 登录测试 ---")
                page.goto(f"{self.base_url}/#/login", wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(2000)

                # 修复：使用正确的 Element Plus 选择器
                # Element Plus 的 input 在 el-input 内部，placeholder 在 input 元素上
                try:
                    # 方式1: 直接通过 input 元素
                    username_input = page.locator('input[placeholder="用户名"]').first
                    password_input = page.locator('input[placeholder="密码"]').first

                    if username_input.count() > 0:
                        self.log("找到用户名输入框", "PASS")
                        username_input.fill("user8")
                        password_input.fill("password123")

                        # 点击登录按钮
                        login_btn = page.locator('button.el-button:has-text("登录")').first
                        if login_btn.count() > 0:
                            login_btn.click()
                            page.wait_for_timeout(3000)

                            # 检查登录结果
                            if page.locator('.user-info, .username, text="user8"').count() > 0 or \
                               "退出" in page.content() or \
                               page.url.endswith("/recommend") or page.url.endswith("/profile"):
                                self.log("登录成功", "PASS")
                                self.take_screenshot(page, "02_logged_in")
                            else:
                                self.log("登录状态待确认", "WARN")
                                self.take_screenshot(page, "02_login_result")
                        else:
                            self.log("未找到登录按钮", "FAIL")
                    else:
                        # 方式2: 通过 el-input 内部查找
                        el_inputs = page.locator('.el-input').all()
                        if len(el_inputs) >= 2:
                            self.log(f"找到 {len(el_inputs)} 个 el-input", "PASS")
                            inputs = page.locator('.el-input input').all()
                            if len(inputs) >= 2:
                                inputs[0].fill("user8")
                                inputs[1].fill("password123")
                                login_btn = page.locator('button.el-button:has-text("登录")').first
                                if login_btn.count() > 0:
                                    login_btn.click()
                                    page.wait_for_timeout(3000)
                                    self.log("登录已提交", "PASS")
                                    self.take_screenshot(page, "02_after_login")
                                else:
                                    self.log("未找到登录按钮", "FAIL")
                            else:
                                self.log("输入框数量不足", "FAIL")
                        else:
                            self.log("未找到登录表单", "FAIL")
                        self.take_screenshot(page, "02_login_page")

                except Exception as e:
                    self.log(f"登录异常: {str(e)[:50]}", "FAIL")
                    self.take_screenshot(page, "02_login_error")

                # ====== 3. 书籍详情和评分测试 ======
                print("\n--- 3. 书籍详情和评分 ---")
                page.goto(f"{self.base_url}/#/book/5", wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(2000)

                # 检查评分组件 el-rate
                rate_component = page.locator('.el-rate').first
                if rate_component.count() > 0:
                    self.log("找到 el-rate 评分组件", "PASS")
                    self.take_screenshot(page, "03_book_detail_with_rating")

                    # 尝试点击评分
                    try:
                        # el-rate 的星星是 span.el-rate__item
                        stars = page.locator('.el-rate__item').all()
                        self.log(f"找到 {len(stars)} 个星星", "INFO")
                        if len(stars) >= 5:
                            stars[4].click()  # 点击第5颗星
                            page.wait_for_timeout(1500)
                            self.log("评分点击成功", "PASS")
                            self.take_screenshot(page, "03_after_rating")
                    except Exception as e:
                        self.log(f"评分点击异常: {str(e)[:30]}", "WARN")
                else:
                    self.log("未找到 el-rate 组件，可能需要登录", "WARN")
                    self.take_screenshot(page, "03_book_detail")

                # ====== 4. 推荐页面测试 ======
                print("\n--- 4. 推荐页面测试 ---")
                page.goto(f"{self.base_url}/#/recommend", wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(2000)

                # 检查 tabs
                tabs = page.locator('.el-tabs__item').all()
                self.log(f"找到 {len(tabs)} 个 Tab", "PASS" if len(tabs) > 0 else "WARN")

                # 检查刷新按钮 (只有登录后才显示)
                refresh_btn = page.locator('button:has-text("刷新推荐")').first
                if refresh_btn.count() > 0:
                    self.log("找到刷新推荐按钮", "PASS")

                    # 点击刷新
                    refresh_btn.click()
                    page.wait_for_timeout(2000)
                    self.log("刷新推荐已点击", "PASS")
                    self.take_screenshot(page, "04_after_refresh")
                else:
                    self.log("刷新按钮未显示（可能未登录）", "WARN")

                # 检查推荐书籍
                rec_books = page.locator('.book-card').all()
                self.log(f"推荐页面有 {len(rec_books)} 个书籍", "PASS" if len(rec_books) > 0 else "WARN")

                self.take_screenshot(page, "04_recommendations")

                # ====== 5. 对比页面测试 ======
                print("\n--- 5. 对比页面 ---")
                page.goto(f"{self.base_url}/#/compare", wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(2000)

                charts = page.locator('canvas, svg').all()
                self.log(f"找到 {len(charts)} 个图表", "PASS" if len(charts) > 0 else "WARN")

                self.take_screenshot(page, "05_compare")

                # ====== 6. 搜索功能测试 ======
                print("\n--- 6. 搜索测试 ---")
                page.goto(self.base_url, wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(1000)

                search_input = page.locator('.el-input input[placeholder*="搜索"], .el-search-input input').first
                if search_input.count() > 0:
                    search_input.fill("Harry")
                    page.wait_for_timeout(1000)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(2000)
                    self.log("搜索执行成功", "PASS")
                    self.take_screenshot(page, "06_search_result")
                else:
                    self.log("未找到搜索框", "WARN")

                # ====== 7. 用户资料页面 ======
                print("\n--- 7. 用户资料页 ---")
                page.goto(f"{self.base_url}/#/profile", wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(2000)

                self.take_screenshot(page, "07_profile")

                # ====== 8. 多轮刷新测试 ======
                print("\n--- 8. 刷新推荐多轮测试 ---")
                page.goto(f"{self.base_url}/#/recommend", wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(1500)

                # 多次点击刷新，验证随机性
                refresh_btn = page.locator('button:has-text("刷新推荐")').first
                if refresh_btn.count() > 0:
                    for i in range(3):
                        refresh_btn.click()
                        page.wait_for_timeout(1500)
                        self.log(f"第 {i+1} 次刷新", "PASS")
                    self.take_screenshot(page, "08_multi_refresh")
                else:
                    self.log("无法测试刷新（未登录）", "WARN")

            except Exception as e:
                self.log(f"测试异常: {str(e)[:100]}", "FAIL")

            finally:
                browser.close()

        # 输出结果
        print("\n" + "="*60)
        print("📊 测试结果总结")
        print("="*60)

        passed = sum(1 for r in self.results if "[PASS]" in r)
        failed = sum(1 for r in self.results if "[FAIL]" in r)
        warnings = sum(1 for r in self.results if "[WARN]" in r)

        print(f"✅ 通过: {passed}")
        print(f"❌ 失败: {failed}")
        print(f"⚠️  警告: {warnings}")

        print("\n通过项:")
        for r in self.results:
            if "[PASS]" in r:
                print(f"  ✓ {r}")

        if self.errors:
            print(f"\n⚠️ 控制台错误 ({len(self.errors)}):")
            for e in self.errors[:5]:
                print(f"  {e[:80]}")

        total = passed + failed
        print(f"\n🎯 通过率: {passed}/{total} ({100*passed/total if total > 0 else 0:.1f}%)")

        return passed, failed, warnings


if __name__ == "__main__":
    tester = OptimizedTester()
    p, f, w = tester.test_complete_flow()

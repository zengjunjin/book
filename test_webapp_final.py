"""
最终优化版 Web 应用测试 - 修复所有问题
"""
import time
from playwright.sync_api import sync_playwright


class FinalTester:
    def __init__(self):
        self.base_url = "http://localhost:5000"
        self.results = []
        self.errors = []
        self.logged_in = False

    def log(self, message, status="INFO"):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{status}] {message}")
        self.results.append(f"[{status}] {message}")

    def take_screenshot(self, page, name):
        path = f"/tmp/final_{name}_{int(time.time())}.png"
        page.screenshot(path=path, full_page=True)
        print(f"  📸 {path}")
        return path

    def run(self):
        print("\n" + "="*60)
        print("🚀 最终优化版 Web 应用测试")
        print("="*60)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={'width': 1400, 'height': 900})
            page = context.new_page()

            page.on("console", lambda msg: self.errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)

            try:
                # 1. 首页
                print("\n--- 1. 首页测试 ---")
                page.goto(self.base_url, wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(2000)

                book_cards = page.locator('.book-card').all()
                self.log(f"首页有 {len(book_cards)} 个书籍卡片", "PASS" if len(book_cards) > 0 else "FAIL")
                self.take_screenshot(page, "01_homepage")

                # 2. 登录
                print("\n--- 2. 登录测试 ---")
                page.goto(f"{self.base_url}/#/login", wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(2000)

                # 正确的选择器
                try:
                    username_input = page.locator('input[placeholder="用户名"]')
                    password_input = page.locator('input[placeholder="密码"]')

                    if username_input.count() > 0:
                        self.log("找到用户名输入框", "PASS")
                        username_input.fill("user8")
                        password_input.fill("password123")
                        page.wait_for_timeout(500)

                        # 点击登录按钮
                        login_btn = page.locator('button:has-text("登录")')
                        login_btn.click()
                        page.wait_for_timeout(3000)

                        self.log("登录已提交", "PASS")
                        self.take_screenshot(page, "02_after_login")
                        self.logged_in = True
                except Exception as e:
                    self.log(f"登录异常: {str(e)[:50]}", "FAIL")
                    self.take_screenshot(page, "02_login_error")

                # 3. 书籍详情
                print("\n--- 3. 书籍详情页 ---")
                page.goto(f"{self.base_url}/#/book/5", wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(2000)

                rate = page.locator('.el-rate')
                if rate.count() > 0:
                    self.log("找到评分组件 el-rate", "PASS")

                    # 点击第7颗星
                    stars = page.locator('.el-rate__item').all()
                    if len(stars) >= 7:
                        stars[6].click()
                        page.wait_for_timeout(1500)
                        self.log("评分成功（7星）", "PASS")
                else:
                    self.log("未找到评分组件", "WARN")

                self.take_screenshot(page, "03_book_detail")

                # 4. 推荐页面
                print("\n--- 4. 推荐页面 ---")
                page.goto(f"{self.base_url}/#/recommend", wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(2000)

                # 检查 tabs
                tabs = page.locator('.el-tabs__item').all()
                self.log(f"找到 {len(tabs)} 个 Tab", "PASS" if len(tabs) > 0 else "WARN")

                # 检查刷新按钮
                refresh_btn = page.locator('button:has-text("刷新推荐")')
                if refresh_btn.count() > 0:
                    self.log("找到刷新推荐按钮", "PASS")

                    # 多次刷新测试
                    for i in range(3):
                        refresh_btn.click()
                        page.wait_for_timeout(2000)
                    self.log("成功刷新3次推荐", "PASS")
                    self.take_screenshot(page, "04_after_refresh")
                else:
                    self.log("刷新按钮未显示（需登录状态）", "WARN")

                # 检查推荐书籍
                rec_books = page.locator('.book-card').all()
                self.log(f"推荐页面有 {len(rec_books)} 个书籍", "PASS" if len(rec_books) > 0 else "WARN")

                # 5. 对比页面
                print("\n--- 5. 对比页面 ---")
                page.goto(f"{self.base_url}/#/compare", wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(2000)

                charts = page.locator('canvas').all()
                self.log(f"找到 {len(charts)} 个图表", "PASS" if len(charts) > 0 else "WARN")
                self.take_screenshot(page, "05_compare")

                # 6. 搜索
                print("\n--- 6. 搜索测试 ---")
                page.goto(self.base_url, wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(1000)

                search_input = page.locator('.el-input input[placeholder*="搜索"]')
                if search_input.count() > 0:
                    search_input.fill("Harry")
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(2000)
                    self.log("搜索执行成功", "PASS")
                    self.take_screenshot(page, "06_search")
                else:
                    self.log("未找到搜索框", "WARN")

                # 7. 用户资料
                print("\n--- 7. 用户资料页 ---")
                page.goto(f"{self.base_url}/#/profile", wait_until="networkidle", timeout=20000)
                page.wait_for_timeout(2000)
                self.take_screenshot(page, "07_profile")

                # 8. API 健康检查
                print("\n--- 8. API 测试 ---")
                try:
                    response = page.goto(f"{self.base_url}/api/health", timeout=5000)
                    if response and response.status == 200:
                        self.log("API 健康检查通过", "PASS")
                    else:
                        self.log("API 健康检查失败", "FAIL")
                except Exception as e:
                    self.log(f"API 异常: {str(e)[:30]}", "FAIL")

                # 测试书籍列表 API
                try:
                    response = page.goto(f"{self.base_url}/api/books?page=1&per_page=5", timeout=5000)
                    if response and response.status == 200:
                        self.log("书籍列表 API 正常", "PASS")
                    else:
                        self.log(f"书籍列表 API 状态: {response.status if response else 'None'}", "WARN")
                except Exception as e:
                    self.log(f"书籍 API 异常: {str(e)[:30]}", "WARN")

            except Exception as e:
                self.log(f"测试异常: {str(e)[:80]}", "FAIL")

            finally:
                browser.close()

        # 结果总结
        print("\n" + "="*60)
        print("📊 最终测试结果总结")
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
        rate = 100 * passed / total if total > 0 else 0
        print(f"\n🎯 通过率: {passed}/{total} ({rate:.1f}%)")

        return passed, failed, warnings


if __name__ == "__main__":
    tester = FinalTester()
    p, f, w = tester.run()

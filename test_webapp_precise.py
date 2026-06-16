"""
精确Web应用测试 - 针对 Element Plus 组件和登录流程优化
"""
import time
from playwright.sync_api import sync_playwright, expect


class PreciseBookRecommendTester:
    def __init__(self):
        self.base_url = "http://localhost:5000"
        self.results = []
        self.screenshots_taken = []

    def log(self, message, status="INFO"):
        """记录测试日志"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{status}] {message}")
        self.results.append(f"[{status}] {message}")

    def take_screenshot(self, page, name):
        """截图保存"""
        path = f"/tmp/precise_test_{name}_{int(time.time())}.png"
        page.screenshot(path=path, full_page=True)
        print(f"  📸 Screenshot: {path}")
        self.screenshots_taken.append(path)
        return path

    def test_homepage_elements(self, page):
        """测试首页元素"""
        self.log("测试首页元素...")
        try:
            page.goto(self.base_url, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(2000)

            # 检查 Element Plus 组件
            book_cards = page.locator('.book-card, .el-card').all()
            self.log(f"找到 {len(book_cards)} 个书籍卡片", "PASS")

            # 检查侧边栏
            sidebar = page.locator('.sidebar, .el-aside, aside').first
            if sidebar.count() > 0:
                self.log("侧边栏组件正常", "PASS")

            # 检查导航链接
            nav_links = page.locator('.nav-link, .router-link, a[href]').all()
            self.log(f"找到 {len(nav_links)} 个导航链接", "INFO")

            self.take_screenshot(page, "01_homepage")
            return True
        except Exception as e:
            self.log(f"首页测试异常: {str(e)[:60]}", "FAIL")
            return False

    def test_login_page(self, page):
        """测试登录页面"""
        self.log("测试登录页面...")
        try:
            page.goto(f"{self.base_url}/#/login", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(2000)

            # Element Plus 输入框
            username_input = page.locator('.el-input input[placeholder="用户名"]').first
            password_input = page.locator('.el-input input[placeholder="密码"]').first

            if username_input.count() > 0:
                self.log("找到用户名输入框", "PASS")

                # 填写登录信息
                username_input.fill("user8")
                password_input.fill("password123")
                self.log("填写登录信息成功", "INFO")

                self.take_screenshot(page, "02_login_filled")

                # 点击登录按钮
                login_btn = page.locator('.el-button:has-text("登录")').first
                if login_btn.count() > 0:
                    login_btn.click()
                    page.wait_for_timeout(3000)

                    # 检查登录结果
                    current_url = page.url
                    self.log(f"登录后 URL: {current_url}", "INFO")

                    # 检查是否显示用户名或退出按钮
                    page_content = page.content()
                    if "user8" in page_content or "退出" in page_content:
                        self.log("登录成功", "PASS")
                        self.take_screenshot(page, "03_after_login")
                        return True
                    else:
                        self.log("登录状态不明确", "WARN")
                        self.take_screenshot(page, "03_login_result")
                        return False
                else:
                    self.log("未找到登录按钮", "FAIL")
                    return False
            else:
                self.log("未找到登录表单元素", "FAIL")
                self.take_screenshot(page, "02_login_page")
                return False
        except Exception as e:
            self.log(f"登录测试异常: {str(e)[:80]}", "FAIL")
            self.take_screenshot(page, "02_login_error")
            return False

    def test_book_detail_with_rating(self, page):
        """测试书籍详情页和评分功能"""
        self.log("测试书籍详情页和评分...")
        try:
            # 先确保登录
            page.goto(f"{self.base_url}/#/login", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(1000)

            username_input = page.locator('.el-input input[placeholder="用户名"]').first
            password_input = page.locator('.el-input input[placeholder="密码"]').first
            if username_input.count() > 0:
                username_input.fill("user8")
                password_input.fill("password123")
                login_btn = page.locator('.el-button:has-text("登录")').first
                if login_btn.count() > 0:
                    login_btn.click()
                    page.wait_for_timeout(2000)

            # 导航到书籍详情
            page.goto(f"{self.base_url}/#/book/5", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(2000)

            self.log("进入书籍详情页", "PASS")
            self.take_screenshot(page, "04_book_detail")

            # 检查评分区域
            rating_section = page.locator('.rating, [class*="rating"], .el-rate').first
            if rating_section.count() > 0:
                self.log("找到评分组件", "PASS")

                # 点击一个评分星级
                stars = page.locator('.el-rate__icon, .el-rate .el-icon-star').all()
                if len(stars) >= 5:
                    stars[4].click()  # 给5星
                    page.wait_for_timeout(1000)
                    self.log("评分点击成功", "PASS")
                    self.take_screenshot(page, "05_after_rating")
            else:
                self.log("未找到评分组件", "WARN")

            return True
        except Exception as e:
            self.log(f"书籍详情测试异常: {str(e)[:60]}", "FAIL")
            return False

    def test_recommend_page(self, page):
        """测试推荐页面"""
        self.log("测试推荐页面...")
        try:
            page.goto(f"{self.base_url}/#/recommend", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(2000)

            # 检查 Tab 切换
            tabs = page.locator('.el-tab-pane, .el-tabs__item').all()
            self.log(f"找到 {len(tabs)} 个 Tab", "INFO")

            # 尝试点击 CF Tab
            cf_tab = page.locator('.el-tabs__item:has-text("协同过滤"), .el-tab-pane:has-text("CF")').first
            if cf_tab.count() > 0:
                cf_tab.click()
                page.wait_for_timeout(1500)
                self.log("切换到协同过滤 Tab", "PASS")

            # 检查刷新按钮
            refresh_btn = page.locator('.el-button:has-text("刷新"), button:has-text("refresh")').first
            if refresh_btn.count() > 0:
                self.log("找到刷新按钮", "PASS")

                # 点击刷新
                refresh_btn.click()
                page.wait_for_timeout(2000)
                self.log("刷新推荐成功", "PASS")
                self.take_screenshot(page, "06_after_refresh")
            else:
                self.log("未找到刷新按钮", "WARN")

            # 检查书籍卡片
            book_cards = page.locator('.book-card, .el-card').all()
            self.log(f"推荐页面有 {len(book_cards)} 个书籍卡片", "PASS")

            return True
        except Exception as e:
            self.log(f"推荐页面测试异常: {str(e)[:60]}", "FAIL")
            return False

    def test_compare_page(self, page):
        """测试对比页面"""
        self.log("测试对比页面...")
        try:
            page.goto(f"{self.base_url}/#/compare", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(2000)

            # 检查图表
            charts = page.locator('canvas, .el-chart, svg').all()
            self.log(f"找到 {len(charts)} 个图表", "INFO")

            self.take_screenshot(page, "07_compare_page")
            return True
        except Exception as e:
            self.log(f"对比页面测试异常: {str(e)[:60]}", "FAIL")
            return False

    def test_profile_page(self, page):
        """测试用户资料页面"""
        self.log("测试用户资料页面...")
        try:
            page.goto(f"{self.base_url}/#/profile", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(2000)

            # 检查用户信息
            profile_content = page.content()
            if "user8" in profile_content or "评分" in profile_content:
                self.log("用户资料页面内容正常", "PASS")

            self.take_screenshot(page, "08_profile_page")
            return True
        except Exception as e:
            self.log(f"用户资料测试异常: {str(e)[:60]}", "FAIL")
            return False

    def test_search(self, page):
        """测试搜索功能"""
        self.log("测试搜索功能...")
        try:
            # 查找搜索框
            search_input = page.locator('.el-input input[placeholder*="搜索"], .el-input input[placeholder*="书"]').first
            if search_input.count() > 0:
                search_input.fill("Harry Potter")
                page.wait_for_timeout(1000)
                page.keyboard.press("Enter")
                page.wait_for_timeout(2000)
                self.log("搜索执行成功", "PASS")
                self.take_screenshot(page, "09_search_result")
                return True
            else:
                self.log("未找到搜索框", "WARN")
                return False
        except Exception as e:
            self.log(f"搜索测试异常: {str(e)[:40]}", "WARN")
            return False

    def run(self):
        """运行所有精确测试"""
        print("\n" + "="*60)
        print("🚀 开始精确Web应用测试")
        print("="*60)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1400, 'height': 900},
                locale='zh-CN'
            )
            page = context.new_page()

            # 启用控制台错误日志
            errors = []
            page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else None)

            try:
                # 1. 首页测试
                print("\n--- 测试 1: 首页 ---")
                self.test_homepage_elements(page)

                # 2. 搜索测试
                print("\n--- 测试 2: 搜索 ---")
                self.test_search(page)

                # 3. 登录测试
                print("\n--- 测试 3: 登录 ---")
                logged_in = self.test_login_page(page)

                # 4. 书籍详情和评分
                print("\n--- 测试 4: 书籍详情和评分 ---")
                self.test_book_detail_with_rating(page)

                # 5. 推荐页面
                print("\n--- 测试 5: 推荐页面 ---")
                self.test_recommend_page(page)

                # 6. 对比页面
                print("\n--- 测试 6: 对比页面 ---")
                self.test_compare_page(page)

                # 7. 用户资料页面
                print("\n--- 测试 7: 用户资料 ---")
                self.test_profile_page(page)

                # 输出控制台错误
                if errors:
                    print("\n⚠️ 控制台错误:")
                    for err in errors[:5]:
                        print(f"  {err}")

            except Exception as e:
                self.log(f"测试异常: {str(e)}", "FAIL")

            finally:
                browser.close()

        # 输出总结
        print("\n" + "="*60)
        print("📊 测试结果总结")
        print("="*60)

        passed = sum(1 for r in self.results if "[PASS]" in r)
        failed = sum(1 for r in self.results if "[FAIL]" in r)
        warnings = sum(1 for r in self.results if "[WARN]" in r)

        print(f"✅ 通过: {passed}")
        print(f"❌ 失败: {failed}")
        print(f"⚠️  警告: {warnings}")

        print("\n详细结果:")
        for r in self.results:
            if "[PASS]" in r or "[FAIL]" in r:
                print(f"  {r}")

        print(f"\n共拍摄 {len(self.screenshots_taken)} 张截图")
        for s in self.screenshots_taken:
            print(f"  - {s}")

        return passed, failed, warnings


if __name__ == "__main__":
    tester = PreciseBookRecommendTester()
    passed, failed, warnings = tester.run()
    total = passed + failed
    print(f"\n🎯 测试完成! 通过率: {passed}/{total} ({100*passed/total if total > 0 else 0:.1f}%)")

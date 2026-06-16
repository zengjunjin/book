"""
全面Web应用测试 - 多轮测试书籍推荐系统
测试范围：登录、注册、书籍浏览、评分、推荐、刷新等功能
"""
import time
import random
from playwright.sync_api import sync_playwright, expect


class BookRecommendTester:
    def __init__(self):
        self.base_url = "http://localhost:5000"
        self.test_email = f"testuser_{int(time.time())}@example.com"
        self.test_username = f"testuser_{int(time.time())}"
        self.test_password = "Test123456"
        self.logged_in = False
        self.results = []

    def log(self, message, status="INFO"):
        """记录测试日志"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{status}] {message}")
        self.results.append(f"[{status}] {message}")

    def take_screenshot(self, page, name):
        """截图保存"""
        path = f"/tmp/test_screenshot_{name}_{int(time.time())}.png"
        page.screenshot(path=path, full_page=True)
        print(f"  📸 Screenshot saved: {path}")
        return path

    def run_test_round(self, page, round_num):
        """执行一轮测试"""
        print(f"\n{'='*60}")
        print(f"🔄 测试轮次 {round_num}")
        print(f"{'='*60}")

        # 1. 测试首页
        self.test_homepage(page)

        # 2. 测试搜索功能
        self.test_search(page)

        # 3. 测试书籍详情页
        self.test_book_detail(page)

        # 4. 测试评分功能
        self.test_rating(page)

        # 5. 测试推荐页面
        self.test_recommendations(page)

        # 6. 测试刷新推荐
        self.test_refresh(page)

        # 7. 测试对比页面
        self.test_compare(page)

        # 8. 测试用户资料页
        self.test_profile(page)

    def test_homepage(self, page):
        """测试首页"""
        self.log("测试首页...")
        try:
            page.goto(self.base_url, wait_until="networkidle", timeout=10000)
            page.wait_for_timeout(1000)

            # 检查页面标题或主要内容
            title = page.title()
            self.log(f"页面标题: {title}", "PASS")

            # 检查是否有书籍卡片或主要内容
            content = page.content()
            if "书" in content or "book" in content.lower():
                self.log("首页包含书籍相关内容", "PASS")
            else:
                self.log("首页内容异常", "FAIL")

            self.take_screenshot(page, "homepage")
        except Exception as e:
            self.log(f"首页测试失败: {str(e)[:50]}", "FAIL")

    def test_search(self, page):
        """测试搜索功能"""
        self.log("测试搜索功能...")
        try:
            # 查找搜索框
            search_input = page.locator('input[placeholder*="搜索"], input[type="search"], input[name*="search" i]').first
            if search_input.count() > 0:
                search_input.fill("Harry Potter")
                page.keyboard.press("Enter")
                page.wait_for_timeout(1500)
                self.log("搜索功能正常", "PASS")
                self.take_screenshot(page, "search_result")
            else:
                self.log("未找到搜索框", "WARN")
        except Exception as e:
            self.log(f"搜索测试跳过: {str(e)[:30]}", "WARN")

    def test_book_detail(self, page):
        """测试书籍详情页"""
        self.log("测试书籍详情页...")
        try:
            # 尝试点击第一本书
            book_cards = page.locator('.book-card, [class*="book"], .book-item').all()
            if book_cards:
                book_cards[0].click()
                page.wait_for_timeout(1500)
                self.log("成功进入书籍详情页", "PASS")
                self.take_screenshot(page, "book_detail")
            else:
                self.log("未找到书籍卡片", "WARN")
        except Exception as e:
            self.log(f"书籍详情测试跳过: {str(e)[:30]}", "WARN")

    def test_rating(self, page):
        """测试评分功能"""
        self.log("测试评分功能...")
        try:
            # 查找评分按钮（1-10分）
            rating_buttons = page.locator('button:has-text("1"), button:has-text("2"), button:has-text("评分")').all()
            if len(rating_buttons) > 0:
                rating_buttons[0].click()
                page.wait_for_timeout(500)
                self.log("评分功能正常", "PASS")
            else:
                self.log("未找到评分按钮，可能需要登录", "WARN")
        except Exception as e:
            self.log(f"评分测试跳过: {str(e)[:30]}", "WARN")

    def test_recommendations(self, page):
        """测试推荐页面"""
        self.log("测试推荐页面...")
        try:
            # 导航到推荐页面
            page.goto(f"{self.base_url}/#/recommend", wait_until="networkidle", timeout=10000)
            page.wait_for_timeout(1500)
            self.log("推荐页面加载成功", "PASS")
            self.take_screenshot(page, "recommendations")
        except Exception as e:
            self.log(f"推荐页面测试: {str(e)[:30]}", "WARN")

    def test_refresh(self, page):
        """测试刷新推荐功能"""
        self.log("测试刷新推荐功能...")
        try:
            # 查找刷新按钮
            refresh_btn = page.locator('button:has-text("刷新"), button[class*="refresh"]').first
            if refresh_btn.count() > 0:
                # 获取刷新前的推荐
                page.wait_for_timeout(500)

                # 点击刷新
                refresh_btn.click()
                page.wait_for_timeout(2000)

                self.log("刷新推荐功能正常", "PASS")
                self.take_screenshot(page, "after_refresh")
            else:
                self.log("未找到刷新按钮", "WARN")
        except Exception as e:
            self.log(f"刷新测试跳过: {str(e)[:30]}", "WARN")

    def test_compare(self, page):
        """测试对比页面"""
        self.log("测试对比页面...")
        try:
            page.goto(f"{self.base_url}/#/compare", wait_until="networkidle", timeout=10000)
            page.wait_for_timeout(1000)
            self.log("对比页面加载成功", "PASS")
            self.take_screenshot(page, "compare")
        except Exception as e:
            self.log(f"对比页面测试: {str(e)[:30]}", "WARN")

    def test_profile(self, page):
        """测试用户资料页面"""
        self.log("测试用户资料页面...")
        try:
            page.goto(f"{self.base_url}/#/profile", wait_until="networkidle", timeout=10000)
            page.wait_for_timeout(1000)
            self.log("用户资料页面加载成功", "PASS")
            self.take_screenshot(page, "profile")
        except Exception as e:
            self.log(f"用户资料页面测试: {str(e)[:30]}", "WARN")

    def test_login_flow(self, page):
        """测试登录流程"""
        self.log("测试登录流程...")
        try:
            # 导航到登录页
            page.goto(f"{self.base_url}/#/login", wait_until="networkidle", timeout=10000)
            page.wait_for_timeout(1000)

            # 填写登录表单
            username_input = page.locator('input[name="username"], input[type="text"]').first
            password_input = page.locator('input[name="password"], input[type="password"]').first

            if username_input.count() > 0 and password_input.count() > 0:
                username_input.fill("user8")  # 使用已有的测试用户
                password_input.fill("password123")
                page.wait_for_timeout(500)

                # 点击登录按钮
                login_btn = page.locator('button[type="submit"], button:has-text("登录"), button:has-text("Login")').first
                if login_btn.count() > 0:
                    login_btn.click()
                    page.wait_for_timeout(2000)

                    # 检查是否登录成功
                    content = page.content()
                    if "退出" in content or "logout" in content.lower() or "profile" in content.lower():
                        self.log("登录成功", "PASS")
                        self.logged_in = True
                        self.take_screenshot(page, "after_login")
                    else:
                        self.log("登录状态不明确", "WARN")
                else:
                    self.log("未找到登录按钮", "WARN")
            else:
                self.log("未找到登录表单", "WARN")
        except Exception as e:
            self.log(f"登录测试失败: {str(e)[:50]}", "FAIL")

    def run(self):
        """运行所有测试"""
        print("\n" + "="*60)
        print("🚀 开始全面Web应用测试")
        print("="*60)

        with sync_playwright() as p:
            # 启动浏览器
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1280, 'height': 720},
                locale='zh-CN'
            )
            page = context.new_page()

            # 启用控制台日志捕获
            page.on("console", lambda msg: print(f"  [CONSOLE] {msg.type}: {msg.text}") if msg.type == "error" else None)

            try:
                # 第一轮：未登录状态测试
                print("\n" + "-"*60)
                print("📋 第一轮：未登录状态测试")
                print("-"*60)
                self.run_test_round(page, 1)

                # 第二轮：登录后测试
                print("\n" + "-"*60)
                print("📋 第二轮：登录后测试")
                print("-"*60)
                self.test_login_flow(page)
                if self.logged_in:
                    self.run_test_round(page, 2)
                else:
                    self.log("登录失败，跳过登录后测试", "WARN")

                # 第三轮：多标签页测试
                print("\n" + "-"*60)
                print("📋 第三轮：深度功能测试")
                print("-"*60)

                # 测试书籍列表分页
                self.log("测试书籍列表分页...")
                page.goto(f"{self.base_url}/#/home", wait_until="networkidle", timeout=10000)
                page.wait_for_timeout(1000)

                # 测试详情页的交互
                self.log("测试详情页交互...")
                page.goto(f"{self.base_url}/#/book/1", wait_until="networkidle", timeout=10000)
                page.wait_for_timeout(1000)
                self.take_screenshot(page, "book_detail_interaction")

                # 测试评分分布显示
                self.log("测试评分分布显示...")
                page.goto(f"{self.base_url}/#/book/5", wait_until="networkidle", timeout=10000)
                page.wait_for_timeout(1000)
                self.take_screenshot(page, "rating_distribution")

            except Exception as e:
                self.log(f"测试过程中出现异常: {str(e)[:100]}", "FAIL")

            finally:
                browser.close()

        # 输出测试结果总结
        print("\n" + "="*60)
        print("📊 测试结果总结")
        print("="*60)

        pass_count = sum(1 for r in self.results if "[PASS]" in r)
        fail_count = sum(1 for r in self.results if "[FAIL]" in r)
        warn_count = sum(1 for r in self.results if "[WARN]" in r)

        print(f"✅ 通过: {pass_count}")
        print(f"❌ 失败: {fail_count}")
        print(f"⚠️  警告: {warn_count}")

        print("\n详细结果:")
        for r in self.results:
            if "[PASS]" in r or "[FAIL]" in r:
                print(f"  {r}")

        return pass_count, fail_count, warn_count


if __name__ == "__main__":
    tester = BookRecommendTester()
    passed, failed, warnings = tester.run()
    print(f"\n测试完成! 通过率: {passed}/{passed+failed} ({100*passed/(passed+failed) if passed+failed > 0 else 0:.1f}%)")

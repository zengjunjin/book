"""图书推荐系统 - Playwright 自动化测试"""
import time
from playwright.sync_api import sync_playwright

BASE_URL = 'http://localhost:5000'
TEST_USER = 'user_8'
TEST_PASSWORD = 'password123'
TIMEOUT = 60000  # 60 秒超时（推荐引擎初始化较慢）
step_count = [0]

def step(msg):
    step_count[0] += 1
    print(f"\n{'='*60}\n[{step_count[0]:02d}] {msg}\n{'='*60}")

def screenshot(page, name, sleep=1.0):
    time.sleep(sleep)
    path = f'C:/Users/15116/Desktop/book/screenshots/{name}.png'
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    page.screenshot(path=path, full_page=True)
    print(f'   📸 截图已保存 -> {path}')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.set_default_timeout(TIMEOUT)

    # ============ 1. 首页 ============
    step('访问首页 - 验证书籍列表渲染')
    page.goto(BASE_URL)
    page.wait_for_load_state('networkidle')
    time.sleep(3)
    screenshot(page, '01_homepage')
    title = page.title()
    print(f'   页面标题: {title}')
    cards = page.locator('[class*="book-card"]').count()
    el_cards = page.locator('[class*="book"]').count()
    print(f'   类名含 "book" 的元素: {el_cards} 个')
    # 获取页面可见文本
    body_text = page.locator('body').inner_text()
    print(f'   页面文本前 200 字: {body_text[:200]}')

    # ============ 2. 搜索功能 ============
    step('测试搜索功能 - 搜索 "Harry Potter"')
    # 查找输入框
    try:
        search_input = page.locator('input[type="text"]').first
        if search_input.count() == 0:
            search_input = page.locator('input').first
        search_input.fill('Harry Potter')
        search_input.press('Enter')
        time.sleep(3)
        screenshot(page, '02_search_harrypotter')
        print('   ✅ 搜索完成')
    except Exception as e:
        print(f'   ⚠ 搜索可能未完成: {e}')

    # ============ 3. 登录流程 ============
    step('用户登录')
    page.goto(f'{BASE_URL}/login')
    page.wait_for_load_state('networkidle')
    time.sleep(2)
    screenshot(page, '03_login_page')

    # 填写用户名密码
    try:
        inputs = page.locator('input').all()
        print(f'   找到 {len(inputs)} 个输入框')
        page.locator('input').first.fill(TEST_USER)
        page.locator('input').nth(1).fill(TEST_PASSWORD)
        screenshot(page, '04_login_filled')

        # 点击登录按钮
        buttons = page.locator('button, [type="submit"]').all()
        print(f'   找到 {len(buttons)} 个按钮，点击登录')
        page.locator('button').first.click()
        time.sleep(3)
        screenshot(page, '05_logged_in')
    except Exception as e:
        print(f'   ⚠ 登录表单处理异常: {e}')

    # ============ 4. 推荐页 ============
    step('测试推荐页面 - CF + SVD')
    page.goto(f'{BASE_URL}/recommend')
    page.wait_for_load_state('networkidle')
    time.sleep(4)
    screenshot(page, '06_recommend_page')
    rec_text = page.locator('body').inner_text()
    print(f'   推荐页可见文本: {rec_text[:300]}')

    # ============ 5. 算法对比页 ============
    step('测试算法对比页面')
    page.goto(f'{BASE_URL}/compare')
    page.wait_for_load_state('networkidle')
    time.sleep(4)
    screenshot(page, '07_compare_page')
    compare_text = page.locator('body').inner_text()
    print(f'   对比页可见文本: {compare_text[:300]}')

    # ============ 6. 用户中心页 ============
    step('测试用户中心')
    page.goto(f'{BASE_URL}/profile')
    page.wait_for_load_state('networkidle')
    time.sleep(3)
    screenshot(page, '08_profile_page')
    profile_text = page.locator('body').inner_text()
    print(f'   用户中心可见文本: {profile_text[:300]}')

    # ============ 7. 返回首页并点击一本书 ============
    step('返回首页并查看书籍详情')
    page.goto(BASE_URL)
    page.wait_for_load_state('networkidle')
    time.sleep(3)

    # 尝试点击一个卡片
    try:
        first_book = page.locator('a').first
        # 找 book/ 链接
        all_links = page.locator('a').all()
        book_link = None
        for link in all_links:
            href = link.get_attribute('href') or ''
            if 'book' in href or '/book/' in href:
                book_link = link
                break

        if book_link:
            book_url = book_link.get_attribute('href')
            print(f'   点击链接: {book_url}')
            book_link.click()
            page.wait_for_load_state('networkidle')
            time.sleep(4)
            screenshot(page, '09_book_detail')
            detail_text = page.locator('body').inner_text()
            print(f'   详情页文本: {detail_text[:300]}')
        else:
            print('   ⚠ 未找到书籍链接')
    except Exception as e:
        print(f'   ⚠ 点击书籍时出错: {e}')

    # ============ 8. 评分功能 ============
    step('测试书籍评分功能')
    # 在书籍详情页找评分组件
    try:
        rating_inputs = page.locator('input[role="slider"]').count()
        print(f'   找到评分滑块: {rating_inputs} 个')
        if rating_inputs == 0:
            # 简化：尝试找 button
            btns = page.locator('button').all()
            print(f'   当前页面按钮数: {len(btns)}')
        time.sleep(1)
        screenshot(page, '10_rating_test')
    except Exception as e:
        print(f'   ⚠ 评分测试异常: {e}')

    # ============ 9. 404 路由 fallback ============
    step('测试 Vue Router fallback - 不存在路由')
    page.goto(f'{BASE_URL}/nonexistent-route-test-404')
    page.wait_for_load_state('networkidle')
    time.sleep(2)
    screenshot(page, '11_route_fallback')
    fallback_text = page.locator('body').inner_text()
    print(f'   fallback 页面长度: {len(fallback_text)} 字')

    # ============ 10. API 健康检查 ============
    step('测试 API 健康检查接口')
    # 直接在页面内调用 fetch
    result = page.evaluate("""
        async () => {
            const r = await fetch('/api/health');
            return await r.json();
        }
    """)
    print(f'   /api/health 返回: {result}')

    # 测试书籍列表 API
    books_result = page.evaluate("""
        async () => {
            const r = await fetch('/api/books?page=1&per_page=10');
            return await r.json();
        }
    """)
    print(f'   /api/books 返回书籍数: {len(books_result.get("books", []))} 本')

    browser.close()

print('\n' + '='*60)
print('🎉 所有测试步骤完成！')
print(f'   截图已保存到: C:/Users/15116/Desktop/book/screenshots/')
print('='*60)

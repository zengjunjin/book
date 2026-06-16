"""图书推荐系统 - 更细致的 Playwright 测试"""
import time
from playwright.sync_api import sync_playwright

BASE_URL = 'http://localhost:5000'
TEST_USER = 'user_8'
TEST_PASSWORD = 'password123'
TIMEOUT = 60000
step_count = [0]

def step(msg):
    step_count[0] += 1
    print(f"\n{'='*60}\n[{step_count[0]:02d}] {msg}")

def screenshot(page, name, wait=2.0):
    time.sleep(wait)
    path = f'C:/Users/15116/Desktop/book/screenshots/{name}.png'
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    page.screenshot(path=path, full_page=True)
    print(f'   📸 {name}.png')

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={'width': 1440, 'height': 900})
    page = context.new_page()
    page.set_default_timeout(TIMEOUT)

    # ============ 1. 登录 ============
    step('登录 user_8 / password123')
    page.goto(f'{BASE_URL}/login')
    page.wait_for_load_state('networkidle')
    screenshot(page, 'a01_login_page')

    inputs = page.locator('input').all()
    print(f'   找到 {len(inputs)} 个输入框')
    page.locator('input').first.fill(TEST_USER)
    page.locator('input').nth(1).fill(TEST_PASSWORD)

    # 点击登录按钮
    page.locator('button').first.click()
    page.wait_for_load_state('networkidle')
    screenshot(page, 'a02_after_login')
    current_url = page.url
    print(f'   登录后 URL: {current_url}')

    # ============ 2. 首页书籍列表 ============
    step('首页 - 滚动查看书籍列表')
    page.goto(BASE_URL)
    page.wait_for_load_state('networkidle')
    time.sleep(2)
    screenshot(page, 'a03_home_page')
    page_text = page.locator('body').inner_text()
    print(f'   首页包含标题: {"书籍广场" in page_text}')
    print(f'   首页第一本书: {page_text.split(chr(10))[2] if len(page_text.split(chr(10))) > 2 else "N/A"}')

    # 向下滚动
    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    time.sleep(1)
    screenshot(page, 'a04_home_scrolled')

    # ============ 3. 点击第一个书籍卡片 ============
    step('点击首页第一个书籍卡片')
    page.goto(BASE_URL)
    page.wait_for_load_state('networkidle')
    time.sleep(2)

    # 找到第一个类名含 book 的卡片并点击
    first_card = page.locator('[class*="book-card"]').first
    if first_card.count() > 0:
        print(f'   找到 book-card 元素，准备点击')
        first_card.click()
        page.wait_for_load_state('networkidle')
        time.sleep(3)
        screenshot(page, 'a05_book_detail_click')
        print(f'   当前 URL: {page.url}')
    else:
        # 用 JS 触发 router.push
        print('   未找到 book-card，尝试直接访问一本已知的书')
        page.goto(f'{BASE_URL}/book/1')
        page.wait_for_load_state('networkidle')
        time.sleep(3)
        screenshot(page, 'a05_book_detail_direct')
        print(f'   访问 /book/1 后 URL: {page.url}')

    detail_text = page.locator('body').inner_text()
    print(f'   详情页内容长度: {len(detail_text)} 字')
    print(f'   详情页前 300 字: {detail_text[:300]}')

    # ============ 4. 评分测试 ============
    step('在书籍详情页测试评分功能')
    time.sleep(1)
    screenshot(page, 'a06_detail_before_rate')

    # 找评分组件 (StarFilled / el-rate)
    rate_elements = page.locator('[class*="rate"], [class*="star"]').count()
    print(f'   找到评分组件: {rate_elements} 个')

    # 尝试点击第一颗星
    try:
        star_elements = page.locator('.el-rate__item').all()
        print(f'   el-rate 子项: {len(star_elements)} 个')
        if len(star_elements) >= 5:
            star_elements[4].click()  # 打 5 分
            time.sleep(3)
            screenshot(page, 'a07_after_rating')
            print('   ✅ 评分完成')
    except Exception as e:
        print(f'   ⚠ 评分组件操作异常: {e}')

    # ============ 5. 推荐页 ============
    step('访问推荐页 - CF + SVD 对比')
    page.goto(f'{BASE_URL}/recommend')
    page.wait_for_load_state('networkidle')
    time.sleep(4)
    screenshot(page, 'a08_recommend_page')

    rec_text = page.locator('body').inner_text()
    has_cf = '协同过滤' in rec_text
    has_svd = 'SVD' in rec_text
    print(f'   包含协同过滤标签: {has_cf}')
    print(f'   包含 SVD 标签: {has_svd}')

    # 切换 tab
    try:
        svd_tab = page.locator('text=SVD 矩阵分解').first
        svd_tab.click()
        time.sleep(3)
        screenshot(page, 'a09_svd_tab')
        print('   ✅ 切换到 SVD tab')
    except Exception as e:
        print(f'   ⚠ 切换 tab 异常: {e}')

    # 切换回 CF
    try:
        cf_tab = page.locator('text=协同过滤').first
        cf_tab.click()
        time.sleep(2)
        screenshot(page, 'a10_cf_tab')
        print('   ✅ 切换回 CF tab')
    except Exception as e:
        print(f'   ⚠ 切换 tab 异常: {e}')

    # ============ 6. 刷新推荐 ============
    step('点击刷新推荐按钮')
    try:
        # 查找刷新按钮
        refresh_btn = page.locator('button').nth(0)
        refresh_btn.click()
        time.sleep(5)  # 推荐引擎初始化需要时间
        screenshot(page, 'a11_after_refresh')
        print('   ✅ 刷新推荐请求')
    except Exception as e:
        print(f'   ⚠ 刷新按钮异常: {e}')

    # ============ 7. 算法对比页 ============
    step('算法对比页 - 查看图表')
    page.goto(f'{BASE_URL}/compare')
    page.wait_for_load_state('networkidle')
    time.sleep(4)
    screenshot(page, 'a12_compare_page')
    print(f'   对比页内容长度: {len(page.locator("body").inner_text())} 字')

    # 向下滚动看图表
    page.evaluate("window.scrollTo(0, 500)")
    time.sleep(1)
    screenshot(page, 'a13_compare_charts')

    # ============ 8. 用户中心 ============
    step('用户中心 - 查看评分历史')
    page.goto(f'{BASE_URL}/profile')
    page.wait_for_load_state('networkidle')
    time.sleep(2)
    screenshot(page, 'a14_profile_page')
    profile_text = page.locator('body').inner_text()
    has_user_8 = 'user_8' in profile_text
    has_history = '评分历史' in profile_text
    print(f'   显示用户信息: {has_user_8}')
    print(f'   显示评分历史: {has_history}')

    # ============ 9. 通过前端 API 直接测试后端 ============
    step('前端 API 测试 - 后端响应')
    api_results = page.evaluate("""
        async () => {
            const results = {};
            try {
                const r1 = await fetch('/api/books?page=1&per_page=5');
                results.books = await r1.json();
            } catch(e) { results.books_err = e.message; }

            try {
                const r2 = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: 'user_8', password: 'password123'})
                });
                results.login = await r2.json();
            } catch(e) { results.login_err = e.message; }

            try {
                const r3 = await fetch('/api/recommend/svd?user_id=8&n=5');
                results.svd = await r3.json();
            } catch(e) { results.svd_err = e.message; }

            return results;
        }
    """)
    print(f'   /api/books 返回: {len(api_results.get("books", {}).get("books", []))} 本')
    print(f'   /api/auth/login 成功: {api_results.get("login", {}).get("user") is not None}')
    svd_recs = api_results.get('svd', {}).get('recommendations', [])
    print(f'   /api/recommend/svd 返回: {len(svd_recs)} 个推荐')

    # ============ 10. 侧边栏导航 ============
    step('侧边栏导航测试')
    page.goto(BASE_URL)
    page.wait_for_load_state('networkidle')
    time.sleep(2)
    screenshot(page, 'a15_nav_test')

    # 验证侧边栏有 5 个主要导航
    all_texts = page.locator('body').inner_text()
    has_nav = all(kw in all_texts for kw in ['书籍广场', '为你推荐', '算法对比', '个人中心'])
    print(f'   侧边栏有完整导航: {has_nav}')

    browser.close()

print('\n' + '='*60)
print('🎉 Web App 测试完成')
print('='*60)

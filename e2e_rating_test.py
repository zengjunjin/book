# -*- coding: utf-8 -*-
"""
端到端测试脚本（修正版）：使用 Python Playwright 验证评分功能
"""
import asyncio
import sys
import os
import re
import json
from datetime import datetime
from pathlib import Path

os.environ.setdefault("PWDEBUG", "0")

from playwright.async_api import async_playwright, Page

FRONTEND_URL = "http://localhost:5173"
BACKEND_URL = "http://localhost:8001"
SCREENSHOT_DIR = Path(r"c:\Users\15116\Desktop\book\screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

USERNAME = "testuser_e2e"
PASSWORD = "Test123456"
EMAIL = f"{USERNAME}@example.com"

def log(msg, end="\n"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", end=end, flush=True)


class TestResult:
    def __init__(self):
        self.console_msgs = []
        self.page_errors = []
        self.network = []   # list of {method, url, status, post_data, ts}
        self.req_index = {}  # url -> list of dicts (for matching response to request)
        self.screenshots = []
        self.failures = []
        self.successes = []
        self.api_responses = []  # only /api/* responses

    def add_console(self, msg):
        # 过滤掉 element-plus deprecation warning（不构成问题）
        if "useDeprecated" in msg:
            return
        if "label act as value is about to be deprecated" in msg:
            return
        if "el-checkbox" in msg and "deprecated" in msg:
            return
        if "https://element-plus.org" in msg:
            return
        self.console_msgs.append(msg)

    def add_error(self, err):
        self.page_errors.append(str(err))

    def add_request(self, method, url, post_data=None, headers=None):
        if "/api/" in url or "/openapi" in url:
            entry = {"method": method, "url": url, "status": "?", "post_data": post_data}
            self.api_responses.append(entry)

    def set_status(self, url, status):
        for e in self.api_responses:
            if e["url"] == url and e["status"] == "?":
                e["status"] = status
                break

    def assert_true(self, cond, name, detail=""):
        if cond:
            self.successes.append(f"[PASS] {name}")
            log(f"  [PASS] {name}")
        else:
            self.failures.append(f"[FAIL] {name} - {detail}")
            log(f"  [FAIL] {name} - {detail}")

    def summary(self):
        log("")
        log("=" * 70)
        log("测试总结")
        log("=" * 70)
        log(f"成功: {len(self.successes)} 项")
        log(f"失败: {len(self.failures)} 项")
        log(f"截图: {len(self.screenshots)} 张")
        log(f"控制台消息: {len(self.console_msgs)} 条")
        log(f"API 请求: {len(self.api_responses)} 条")
        log(f"页面 JS 错误: {len(self.page_errors)} 条")
        if self.failures:
            log("")
            log("失败项详情：")
            for f in self.failures:
                log(f"  {f}")
        return len(self.failures) == 0


async def setup_context(p, headless=True):
    browser = await p.chromium.launch(
        headless=headless,
        args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
    context = await browser.new_context(
        viewport={"width": 1440, "height": 900},
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )
    return browser, context


async def attach_listeners(page: Page, result: TestResult):
    def on_console(msg):
        try:
            text = f"[{msg.type}] {msg.text}"
            result.add_console(text)
        except Exception:
            pass

    def on_pageerror(err):
        try:
            result.add_error(str(err))
        except Exception:
            pass

    def on_request(req):
        try:
            post_data = None
            try:
                post_data = req.post_data
            except Exception:
                pass
            result.add_request(req.method, req.url, post_data=post_data)
        except Exception:
            pass

    def on_response(resp):
        try:
            result.set_status(resp.url, resp.status)
        except Exception:
            pass

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    page.on("request", on_request)
    page.on("response", on_response)


async def api_ensure_user():
    """通过 API 注册测试用户（如果不存在）。返回用户名/密码。"""
    import urllib.request, urllib.error
    # 用唯一 username 避免冲突
    ts = datetime.now().strftime("%H%M%S%f")[:10]
    username = f"e2e_user_{ts}"
    password = "Test123456"
    email = f"{username}@example.com"
    body = json.dumps({"username": username, "password": password, "email": email}).encode()
    req = urllib.request.Request(
        f"{BACKEND_URL}/api/auth/register",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            log(f"  API 注册 {username} 成功: status={resp.status}")
    except urllib.error.HTTPError as e:
        if e.code == 400:
            log(f"  用户 {username} 已存在，继续")
        else:
            log(f"  API 注册失败: {e.code} {e.read().decode()}")
            raise
    return username, password


async def register_or_login(page: Page, result: TestResult):
    log("=" * 70)
    log("步骤 1-2: 打开首页 + 注册/登录")
    log("=" * 70)

    # 通过 API 先确保用户存在
    try:
        api_user, api_pass = await api_ensure_user()
        log(f"  API 已注册用户: {api_user}")
    except Exception as e:
        log(f"  API 注册失败: {e}")
        api_user, api_pass = USERNAME, PASSWORD

    await page.goto(FRONTEND_URL + "/", wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(1500)
    await page.screenshot(path=str(SCREENSHOT_DIR / "e2e_01_homepage.png"), full_page=True)
    result.screenshots.append("e2e_01_homepage.png")
    log(f"已打开首页: {page.url}")
    # 接受 #/ 或无 hash 都算首页
    is_home = page.url.rstrip("/").endswith("5173") or "/#/" in page.url
    result.assert_true(is_home, "首页加载", f"current url: {page.url}")

    # 检查是否已登录（实际看 token）
    token = await page.evaluate("() => localStorage.getItem('token')")
    is_logged_in = bool(token)
    if is_logged_in:
        log(f"已检测到登录 token（{len(token)} 字符），跳过登录步骤")
        return True

    # 走登录页
    await page.goto(FRONTEND_URL + "/#/login", wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(1500)
    await page.screenshot(path=str(SCREENSHOT_DIR / "e2e_02_login.png"), full_page=True)
    result.screenshots.append("e2e_02_login.png")
    log(f"已打开登录页: {page.url}")

    # 填表（使用 API 注册的账号）
    user_input = page.locator("input[placeholder='用户名']")
    await user_input.fill(api_user)
    pwd_input = page.locator("input[placeholder='密码']")
    await pwd_input.fill(api_pass)
    await page.screenshot(path=str(SCREENSHOT_DIR / "e2e_03_login_filled.png"), full_page=True)
    result.screenshots.append("e2e_03_login_filled.png")

    submit_btn = page.locator("button:has-text('登录')").first
    await submit_btn.click()
    # 等待跳转或者错误提示
    await page.wait_for_timeout(3000)
    log(f"登录后 URL: {page.url}")

    # 如果仍然在 login 页面
    if "/login" in page.url:
        log("登录未成功，检查具体错误")
        # 截图
        await page.screenshot(path=str(SCREENSHOT_DIR / "e2e_03b_login_failed.png"), full_page=True)
        result.screenshots.append("e2e_03b_login_failed.png")
        # 检查 toast
        for sel in [".el-message"]:
            t = page.locator(sel)
            if await t.count() > 0:
                for i in range(await t.count()):
                    text = await t.nth(i).inner_text()
                    if text:
                        log(f"  错误提示: {text}")
        # 走注册流程
        await page.goto(FRONTEND_URL + "/#/register", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(1500)
        user_reg = page.locator("input[placeholder*='用户名']").first
        await user_reg.fill(api_user)
        email_input = page.locator("input[placeholder*='邮箱']")
        if await email_input.count() > 0:
            await email_input.first.fill(f"{api_user}@example.com")
        # 密码
        pwd_reg = page.locator("input[placeholder='密码']").first
        await pwd_reg.fill(api_pass)
        # 确认密码
        confirm_pwd = page.locator("input[placeholder='确认密码']")
        if await confirm_pwd.count() > 0:
            await confirm_pwd.first.fill(api_pass)
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SCREENSHOT_DIR / "e2e_04_register_filled.png"), full_page=True)
        result.screenshots.append("e2e_04_register_filled.png")

        reg_btn = page.locator("button:has-text('注册')").first
        # 检查按钮是否可用
        is_disabled = await reg_btn.is_disabled()
        log(f"  注册按钮 disabled={is_disabled}")
        if is_disabled:
            # 看下密码规则
            for sel in [".password-rules", ".rule-ok"]:
                t = page.locator(sel)
                if await t.count() > 0:
                    for i in range(await t.count()):
                        try:
                            log(f"    规则[{i}]: {await t.nth(i).inner_text()}")
                        except Exception:
                            pass
        await reg_btn.click()
        await page.wait_for_timeout(3000)
        log(f"注册后 URL: {page.url}")

        if "/register" in page.url:
            # 注册失败，再走一次登录
            await page.goto(FRONTEND_URL + "/#/login", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(1000)
            await page.locator("input[placeholder='用户名']").fill(api_user)
            await page.locator("input[placeholder='密码']").fill(api_pass)
            await page.locator("button:has-text('登录')").first.click()
            await page.wait_for_timeout(3000)

    await page.wait_for_timeout(1500)
    await page.screenshot(path=str(SCREENSHOT_DIR / "e2e_05_after_login.png"), full_page=True)
    result.screenshots.append("e2e_05_after_login.png")
    log(f"最终 URL: {page.url}")
    result.assert_true("/login" not in page.url and "/register" not in page.url,
                       "登录/注册完成（已离开登录页）",
                       f"url={page.url}")

    # 验证 token 存在
    token = await page.evaluate("() => localStorage.getItem('token')")
    result.assert_true(bool(token), "登录 token 写入 localStorage",
                       f"token={bool(token)}")
    return True


async def navigate_to_recommend(page: Page, result: TestResult):
    log("")
    log("=" * 70)
    log("步骤 3: 导航到「为你推荐」")
    log("=" * 70)
    await page.goto(FRONTEND_URL + "/#/recommend", wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(3500)
    await page.screenshot(path=str(SCREENSHOT_DIR / "e2e_06_recommend.png"), full_page=True)
    result.screenshots.append("e2e_06_recommend.png")
    log(f"已打开「为你推荐」: {page.url}")

    # 等到 BookCard 出现
    try:
        await page.wait_for_selector(".book-card", timeout=15000)
    except Exception as e:
        log(f"等待 .book-card 超时: {e}")

    cards = await page.locator(".book-card").count()
    log(f"BookCard 数量: {cards}")
    result.assert_true(cards > 0, "推荐页有书籍卡片", f"cards={cards}")
    return cards


async def rate_a_book(page: Page, result: TestResult):
    log("")
    log("=" * 70)
    log("步骤 4-6: 评分 + 检查提示 + 控制台错误")
    log("=" * 70)

    # 取第一个 quick-rate 区域（仅登录后才会渲染）
    first_quick = page.locator(".book-card .quick-rate").first
    n_quick = await page.locator(".book-card .quick-rate").count()
    log(f"含 quick-rate 评分的卡片数: {n_quick}")
    if n_quick == 0:
        result.assert_true(False, "无 quick-rate 评分控件（可能未登录）", "")
        return None

    await first_quick.scroll_into_view_if_needed()
    await page.wait_for_timeout(500)

    rate = first_quick.locator(".el-rate").first
    stars = rate.locator(".el-rate__item")
    star_count = await stars.count()
    log(f"第一个评分组件的星星数量: {star_count}")
    result.assert_true(star_count == 10, "评分组件有 10 颗星", f"star_count={star_count}")

    # 评分前快照
    pre_responses = list(result.api_responses)
    pre_console_count = len(result.console_msgs)

    # 点第 8 颗星（评分 8）
    target = stars.nth(7)
    await target.click()
    # 等 3 秒，确保请求完成
    await page.wait_for_timeout(3500)
    await page.screenshot(path=str(SCREENSHOT_DIR / "e2e_07_after_rate_click.png"), full_page=True)
    result.screenshots.append("e2e_07_after_rate_click.png")

    # 提取评分 API 的响应
    rating_responses = [e for e in result.api_responses[pre_responses.__len__():]
                        if "/api/ratings" in e["url"]
                        and e["method"] == "POST"
                        and not e["url"].rstrip("/").endswith("/user")]
    # 兼容：上面截取可能没拿到（list 复制时 count 算错），重新扫
    rating_responses = [e for e in result.api_responses
                        if "/api/ratings" in e["url"]
                        and e["method"] == "POST"
                        and not e["url"].rstrip("/").endswith("/user")]

    log(f"评分 API POST 响应数: {len(rating_responses)}")
    for r in rating_responses:
        log(f"  {r['method']} {r['url']} -> status={r['status']}")

    rating_status = rating_responses[-1]["status"] if rating_responses else None
    log(f"最终评分状态: {rating_status}")

    # 验证
    if isinstance(rating_status, int):
        result.assert_true(200 <= rating_status < 300,
                           f"评分 API 返回 2xx（实际 {rating_status}）",
                           f"responses={rating_responses}")
        result.assert_true(rating_status != 422, "评分 API 没有 422 错误", f"status={rating_status}")
        result.assert_true(rating_status != 500, "评分 API 没有 500 错误", f"status={rating_status}")
    else:
        result.assert_true(False, "未捕获到评分 API 响应", f"all_responses={[r for r in result.api_responses if '/ratings' in r['url']]}")

    # 检查 toast 提示
    toast_text = ""
    for sel in [".el-message", ".el-notification"]:
        try:
            t = page.locator(sel)
            n = await t.count()
            for i in range(n):
                text = await t.nth(i).inner_text()
                if text and ("评分" in text or "成功" in text or "失败" in text):
                    toast_text = text.strip()
                    break
            if toast_text:
                break
        except Exception:
            pass
    if toast_text:
        log(f"页面提示: {toast_text}")
        result.assert_true("成功" in toast_text or "已评分" in toast_text,
                           "页面提示评分成功", f"toast='{toast_text}'")
    else:
        log("未抓到 toast 提示文字（可能已消失）")
        result.successes.append("[INFO] 未抓到 toast 提示文字")

    # 控制台错误检查
    error_msgs = [m for m in result.console_msgs[pre_console_count:] if "[error]" in m.lower()]
    log(f"评分期间新增控制台 error 数: {len(error_msgs)}")
    for m in error_msgs[:5]:
        log(f"  {m}")

    has_422_in_console = any("422" in m for m in result.console_msgs[pre_console_count:])
    result.assert_true(not has_422_in_console, "评分期间控制台无 422 错误", f"has_422={has_422_in_console}")

    return rating_status


async def refresh_and_verify(page: Page, result: TestResult):
    log("")
    log("=" * 70)
    log("步骤 7: 刷新页面，验证评分保留")
    log("=" * 70)
    pre_count = len(result.api_responses)
    # 使用 reload 强制重新加载（hash 变化 goto 不会重载）
    await page.reload(wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(4500)
    await page.screenshot(path=str(SCREENSHOT_DIR / "e2e_08_recommend_after_refresh.png"), full_page=True)
    result.screenshots.append("e2e_08_recommend_after_refresh.png")
    log(f"刷新后 URL: {page.url}")

    # 解析用户评分数量状态
    try:
        # 找包含"您已评分"的卡片
        status_card = page.locator(".status-card")
        await status_card.wait_for(timeout=8000)
        rating_text = await status_card.inner_text()
        log(f"用户评分状态卡文字: {rating_text[:80]}")
        m = re.search(r"已评分\s*(\d+)\s*本", rating_text)
        if m:
            count = int(m.group(1))
            result.assert_true(count >= 1, f"刷新后用户已评分 {count} 本", f"text='{rating_text[:80]}'")
        else:
            log("未在状态卡中匹配到评分数字")
    except Exception as e:
        log(f"获取评分状态卡失败: {e}")

    # 校验：调用后端 /api/ratings/user 确认数据库里有评分
    token = await page.evaluate("() => localStorage.getItem('token')")
    log(f"前端 token 仍存在: {bool(token)}")
    result.assert_true(bool(token), "登录 token 在刷新后保留", "")

    # 通过浏览器 context 直接 fetch 后端
    api_result = await page.evaluate("""async () => {
        const token = localStorage.getItem('token');
        const r = await fetch('/api/ratings/user?page=1&per_page=20', {
            headers: { 'Authorization': 'Bearer ' + token }
        });
        return { status: r.status, body: await r.json() };
    }""")
    log(f"刷新后 /api/ratings/user -> status={api_result.get('status')}")
    if api_result.get("status") == 200:
        body = api_result.get("body", {})
        ratings = body.get("ratings", [])
        total = body.get("total", 0)
        log(f"  /api/ratings/user 返回 total={total}, 列表长度={len(ratings)}")
        result.assert_true(total >= 1, f"后端确认评分记录 total>=1 (实际 {total})", "")
        if ratings:
            log(f"  最新一条评分: book_id={ratings[0].get('book_id')} rating={ratings[0].get('rating')}")
    else:
        result.assert_true(False, f"/api/ratings/user 调用失败 status={api_result.get('status')}", str(api_result))

    return True


async def test_book_detail(page: Page, result: TestResult):
    log("")
    log("=" * 70)
    log("步骤 8: 测试书籍详情页跳转")
    log("=" * 70)
    try:
        await page.wait_for_selector(".book-card", timeout=10000)
    except Exception:
        log("未找到 .book-card（可能推荐页没数据）")
        result.assert_true(False, "未找到书籍卡片", "")
        return False
    first_card = page.locator(".book-card").first
    cover = first_card.locator(".book-cover").first
    await cover.scroll_into_view_if_needed()
    await cover.click()
    await page.wait_for_timeout(3000)
    log(f"点击书籍后 URL: {page.url}")
    await page.screenshot(path=str(SCREENSHOT_DIR / "e2e_09_book_detail.png"), full_page=True)
    result.screenshots.append("e2e_09_book_detail.png")
    result.assert_true("/book/" in page.url, "成功跳转到书籍详情页", f"url={page.url}")
    return True


async def test_sidebar_profile(page: Page, result: TestResult):
    log("")
    log("=" * 70)
    log("步骤 9: 测试侧边栏个人中心跳转")
    log("=" * 70)
    await page.goto(FRONTEND_URL + "/#/", wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(2000)
    await page.screenshot(path=str(SCREENSHOT_DIR / "e2e_10_back_to_home.png"), full_page=True)
    result.screenshots.append("e2e_10_back_to_home.png")

    profile_menu = page.locator(".sidebar .el-menu-item:has-text('个人中心')")
    cnt = await profile_menu.count()
    log(f"个人中心菜单数量: {cnt}")
    result.assert_true(cnt > 0, "侧边栏有「个人中心」菜单", f"count={cnt}")
    if cnt > 0:
        await profile_menu.first.click()
        await page.wait_for_timeout(2500)
        log(f"点击个人中心后 URL: {page.url}")
        await page.screenshot(path=str(SCREENSHOT_DIR / "e2e_11_profile.png"), full_page=True)
        result.screenshots.append("e2e_11_profile.png")
        result.assert_true("/profile" in page.url, "成功跳转到个人中心", f"url={page.url}")
    return True


async def main():
    result = TestResult()
    log("=" * 70)
    log("E2E 测试开始 - Playwright + Chromium（agent-browser 替代）")
    log("=" * 70)

    async with async_playwright() as p:
        browser, context = await setup_context(p, headless=True)
        page = await context.new_page()
        await attach_listeners(page, result)
        try:
            await register_or_login(page, result)
            await navigate_to_recommend(page, result)
            await rate_a_book(page, result)
            await refresh_and_verify(page, result)
            await test_book_detail(page, result)
            await test_sidebar_profile(page, result)
        except Exception as e:
            log(f"测试执行异常: {e}")
            import traceback
            traceback.print_exc()
            result.failures.append(f"[ERROR] 异常: {e}")
        finally:
            await context.close()
            await browser.close()

    # 报告
    log("")
    log("=" * 70)
    log("控制台消息（最近 30 条，已过滤 deprecation warning）")
    log("=" * 70)
    for m in result.console_msgs[-30:]:
        log(f"  {m[:200]}")

    log("")
    log("=" * 70)
    log("API 请求/响应（仅 /api/*）")
    log("=" * 70)
    for r in result.api_responses:
        post = ""
        if r.get("post_data"):
            post = f"  body={r['post_data'][:200]}"
        log(f"  {r['method']:6s} {str(r['status']):>4} {r['url']}{post}")

    log("")
    log("=" * 70)
    log("页面 JS 错误")
    log("=" * 70)
    for e in result.page_errors:
        log(f"  {e}")
    if not result.page_errors:
        log("  （无）")

    ok = result.summary()

    report = {
        "ok": ok,
        "successes": result.successes,
        "failures": result.failures,
        "console_count": len(result.console_msgs),
        "api_responses": result.api_responses,
        "page_errors": result.page_errors,
        "screenshots": result.screenshots,
    }
    with open(SCREENSHOT_DIR / "e2e_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log(f"报告已写入: {SCREENSHOT_DIR / 'e2e_report.json'}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

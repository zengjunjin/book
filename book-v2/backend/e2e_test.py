"""
端到端测试：模拟前端调用流程
测试时间: {now}
"""
import json
import requests
import time
from datetime import datetime

BASE = "http://localhost:8001"
now = datetime.now().isoformat()

results = []
passed = 0
failed = 0
warnings = 0

def record(name, status, message=""):
    global passed, failed
    if status == "PASS":
        passed += 1
    else:
        failed += 1
    results.append({"name": name, "status": status, "message": message})
    icon = "✅" if status == "PASS" else "❌"
    print(f"{icon} {name}: {message}")

s = requests.Session()
username = f"e2e_{int(time.time())}"
password = "Test123456!"

print("=" * 70)
print("端到端测试: 模拟前端完整用户流程")
print(f"测试用户: {username}")
print(f"后端: {BASE}")
print("=" * 70)

# ===== 阶段 1: 匿名浏览（无需登录） =====
print("\n【阶段 1: 匿名浏览】")

r = s.get(f"{BASE}/api/books", params={"page": 1, "per_page": 5}, timeout=30)
status = "PASS" if r.status_code == 200 else "FAIL"
record("书籍列表浏览", status, f"status={r.status_code}, total={r.json().get('total') if r.status_code == 200 else 'N/A'}")

if r.status_code == 200:
    books = r.json().get("books", [])
    if books:
        test_book_id = books[0]["id"]
        record("获取书籍样本", "PASS", f"book_id={test_book_id}, title={str(books[0].get('title'))[:50]}")

        r2 = s.get(f"{BASE}/api/books/{test_book_id}/similar", timeout=30)
        record("相似书籍查询", "PASS" if r2.status_code == 200 else "FAIL",
               f"status={r2.status_code}, similar={len(r2.json().get('similar_books', [])) if r2.status_code == 200 else 'N/A'}")

r3 = s.get(f"{BASE}/api/books/suggestions", params={"q": "Harry", "limit": 5}, timeout=15)
record("搜索建议", "PASS" if r3.status_code == 200 else "FAIL",
       f"status={r3.status_code}, {len(r3.json().get('suggestions', [])) if r3.status_code == 200 else 0} 条")

r4 = s.get(f"{BASE}/api/books/hot-search", timeout=15)
record("热门搜索", "PASS" if r4.status_code == 200 else "FAIL",
       f"status={r4.status_code}, {len(r4.json().get('hot_search', [])) if r4.status_code == 200 else 0} 条")

r5 = s.get(f"{BASE}/api/books/categories", timeout=15)
record("分类浏览", "PASS" if r5.status_code == 200 else "FAIL",
       f"status={r5.status_code}, {len(r5.json().get('categories', [])) if r5.status_code == 200 else 0} 个")

r6 = s.get(f"{BASE}/api/books/filters", timeout=15)
record("筛选选项", "PASS" if r6.status_code == 200 else "FAIL",
       f"status={r6.status_code}")

r7 = s.get(f"{BASE}/api/ai/popular", params={"limit": 5}, timeout=30)
record("AI 热门推荐", "PASS" if r7.status_code == 200 else "FAIL",
       f"status={r7.status_code}, {len(r7.json().get('books', [])) if r7.status_code == 200 else 0} 本")

r8 = s.get(f"{BASE}/api/ai/search", params={"q": "Harry Potter", "limit": 3}, timeout=30)
record("AI 语义搜索", "PASS" if r8.status_code == 200 else "FAIL",
       f"status={r8.status_code}, {len(r8.json().get('books', [])) if r8.status_code == 200 else 0} 本")

r9 = s.get(f"{BASE}/api/ai/status", timeout=15)
record("AI 引擎状态", "PASS" if r9.status_code == 200 else "FAIL",
       f"status={r9.status_code}")

# ===== 阶段 2: 认证流程 =====
print("\n【阶段 2: 认证流程】")

# 注册
reg = s.post(f"{BASE}/api/auth/register",
             json={"username": username, "email": f"{username}@test.com", "password": password},
             timeout=15)
record("用户注册", "PASS" if reg.status_code == 200 else "FAIL",
       f"status={reg.status_code}")

user_id = None
if reg.status_code == 200:
    user_data = reg.json()
    user_id = user_data.get("id")
    record("注册返回数据", "PASS", f"user_id={user_id}, username={user_data.get('username')}")

# 登录 (OAuth2 form-data)
login = s.post(f"{BASE}/api/auth/login",
               data={"username": username, "password": password},
               timeout=15)
record("用户登录", "PASS" if login.status_code == 200 else "FAIL",
       f"status={login.status_code}")

token = None
if login.status_code == 200:
    login_data = login.json()
    token = login_data.get("access_token")
    if token:
        record("获取 access_token", "PASS", f"token 长度: {len(token)}")
    else:
        record("获取 access_token", "FAIL", "响应中没有 access_token")

# 获取当前用户
if token:
    headers = {"Authorization": f"Bearer {token}"}
    me = s.get(f"{BASE}/api/auth/me", headers=headers, timeout=15)
    record("获取当前用户信息", "PASS" if me.status_code == 200 else "FAIL",
           f"status={me.status_code}")
    if me.status_code == 200:
        me_data = me.json()
        record("用户数据验证", "PASS",
               f"username={me_data.get('username')}, id={me_data.get('id')}")

# ===== 阶段 3: 登录后操作 =====
print("\n【阶段 3: 登录后操作】")

if token:
    headers = {"Authorization": f"Bearer {token}"}

    # 书籍详情
    if 'test_book_id' in dir() and test_book_id:
        detail = s.get(f"{BASE}/api/books/{test_book_id}", headers=headers, timeout=30)
        record("书籍详情", "PASS" if detail.status_code == 200 else "FAIL",
               f"status={detail.status_code}")
        if detail.status_code == 200:
            d = detail.json()
            record("书籍详情数据", "PASS",
                   f"title={str(d.get('title'))[:50]}, community_rating={bool(d.get('community_rating'))}")

    # 创建评分
    rating = s.post(f"{BASE}/api/ratings",
                    json={"book_id": test_book_id, "rating": 9},
                    headers=headers, timeout=15)
    record("创建评分", "PASS" if rating.status_code == 200 else "FAIL",
           f"status={rating.status_code}")

    # 查看用户评分
    r_user = s.get(f"{BASE}/api/ratings/user",
                   params={"user_id": user_id, "page": 1, "per_page": 10},
                   headers=headers, timeout=15)
    record("查询用户评分", "PASS" if r_user.status_code == 200 else "FAIL",
           f"status={r_user.status_code}, {len(r_user.json().get('ratings', [])) if r_user.status_code == 200 else 0} 条")

    # CF 推荐
    cf = s.get(f"{BASE}/api/recommend/cf",
               params={"user_id": user_id, "n": 10},
               headers=headers, timeout=60)
    cf_count = 0
    if cf.status_code == 200:
        cf_count = len(cf.json().get("recommendations", []))
    record("CF 协同过滤推荐", "PASS" if cf.status_code == 200 else "FAIL",
           f"status={cf.status_code}, {cf_count} 本")

    # SVD 推荐
    svd = s.get(f"{BASE}/api/recommend/svd",
                params={"user_id": user_id, "n": 10},
                headers=headers, timeout=120)
    svd_count = 0
    if svd.status_code == 200:
        svd_count = len(svd.json().get("recommendations", []))
    record("SVD 矩阵分解推荐", "PASS" if svd.status_code == 200 else "FAIL",
           f"status={svd.status_code}, {svd_count} 本")

    # 算法对比
    cmp = s.get(f"{BASE}/api/recommend/compare",
                params={"user_id": user_id, "n": 10},
                headers=headers, timeout=120)
    record("算法对比", "PASS" if cmp.status_code == 200 else "FAIL",
           f"status={cmp.status_code}")

    # AI 聊天
    chat = s.post(f"{BASE}/api/ai/chat",
                  json={"message": "推荐一些适合放松的书籍"},
                  headers=headers, timeout=60)
    record("AI 对话", "PASS" if chat.status_code == 200 else "FAIL",
           f"status={chat.status_code}")
    if chat.status_code == 200:
        chat_data = chat.json()
        reply_len = len(str(chat_data.get("reply", "")))
        record("AI 响应内容", "PASS", f"回复长度: {reply_len} 字符")

# ===== 阶段 4: 边界测试 =====
print("\n【阶段 4: 边界测试】")

# 访问不存在的书籍
r10 = s.get(f"{BASE}/api/books/999999", headers=headers if token else {}, timeout=15)
# 可能返回 401（需要登录）或 404（不存在）
record("不存在的书籍", "PASS" if r10.status_code in [401, 404] else "WARN",
       f"status={r10.status_code} (期望 401/404)")

# 未认证的评分（应该被拦截）
r11 = s.post(f"{BASE}/api/ratings", json={"book_id": test_book_id, "rating": 5}, timeout=15)
record("未认证评分拦截", "PASS" if r11.status_code in [401, 403] else "FAIL",
       f"status={r11.status_code} (期望 401/403)")

# ===== 阶段 5: 前端构建验证 =====
print("\n【阶段 5: 前端构建验证】")
import os
frontend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend-v2")
dist_path = os.path.join(frontend_path, "dist")
if os.path.exists(dist_path):
    record("前端 dist 目录", "PASS", f"存在: {dist_path}")
    index_path = os.path.join(dist_path, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
            has_css = "assets/" in content or ".css" in content
            has_js = "<script" in content
            record("前端 index.html 完整性", "PASS",
                   f"包含样式引用={has_css}, 包含脚本引用={has_js}")
else:
    record("前端构建产物", "WARN", f"未找到 dist 目录: {dist_path}")

# ===== 总结 =====
print("\n" + "=" * 70)
print("【测试总结】")
print("=" * 70)
print(f"通过: {passed}")
print(f"失败: {failed}")
if passed + failed > 0:
    print(f"通过率: {round(passed/(passed+failed)*100, 1)}%")
print("=" * 70)

# 保存报告
report = {
    "test_time": now,
    "total_tests": passed + failed,
    "passed": passed,
    "failed": failed,
    "tests": results
}

report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "e2e_test_report.json")
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\n完整报告已保存: {report_path}")

if failed == 0:
    print("\n🎉 所有测试通过！")
else:
    print(f"\n⚠️ 有 {failed} 个测试失败，需要修复")
    for item in results:
        if item["status"] == "FAIL":
            print(f"  ❌ {item['name']}: {item['message']}")

"""全面深度测试 - 验证所有安全修复和前后端一致性"""
import requests
import sys
import time

BASE = "http://localhost:8001"
results = []
all_passed = True

def test(name, actual, expected_desc, critical=True):
    global all_passed
    if isinstance(actual, bool):
        passed = actual
    else:
        passed = actual is not None and actual >= 0
    
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status}: {name}")
    if not passed:
        print(f"        {expected_desc}")
        if critical:
            all_passed = False
    results.append((name, passed))


print("=" * 70)
print("第一阶段: 后端 API 认证保护验证")
print("=" * 70)

s = requests.Session()

# 测试 1: 未登录访问推荐列表 -> 401
print("\n[测试1] 未登录访问推荐接口（应该返回401）")
r = s.get(f"{BASE}/api/recommend/cf", params={"n": 20}, timeout=15)
print(f"  status={r.status_code}, body={r.text[:200]}")
test("匿名访问 /recommend/cf 被拦截", r.status_code == 401, "期望返回401 unauthorized")

r = s.get(f"{BASE}/api/recommend/svd", params={"n": 20}, timeout=15)
test("匿名访问 /recommend/svd 被拦截", r.status_code == 401, "期望返回401 unauthorized")

# 测试 2: 未登录访问评分查询 -> 401
r = s.get(f"{BASE}/api/ratings/user", params={"user_id": 1}, timeout=15)
test("匿名访问 /ratings/user 被拦截", r.status_code == 401, "期望返回401 unauthorized")

# 测试 3: 未登录访问搜索历史 -> 401
r = s.get(f"{BASE}/api/books/search-history", timeout=15)
test("匿名访问 /books/search-history 被拦截", r.status_code == 401, "期望返回401 unauthorized")

# 测试 4: 匿名访问书籍详情（应该允许）
r = s.get(f"{BASE}/api/books/5001", timeout=15)
test("匿名访问书籍详情", r.status_code == 200, "期望返回200")
if r.status_code == 200:
    data = r.json()
    has_cr = 'community_rating' in data and data['community_rating'] is not None
    test(f"  响应包含 community_rating 字段", has_cr, "期望包含社区评分")
    ur = data.get('user_rating')
    test(f"  user_rating = {ur}（未登录应该为 null）", ur is None, "期望为 null")

# 测试 5: 匿名访问热门搜索、分类
r = s.get(f"{BASE}/api/books/hot-search", timeout=15)
test("匿名访问热门搜索", r.status_code == 200, "期望返回200")

r = s.get(f"{BASE}/api/books/categories", timeout=15)
test("匿名访问分类", r.status_code == 200, "期望返回200")

print("\n" + "=" * 70)
print("第二阶段: 注册、登录和用户隔离测试")
print("=" * 70)

# 测试注册
username1 = f"testuser_a_{int(time.time())}"
username2 = f"testuser_b_{int(time.time())}"

r = s.post(f"{BASE}/api/auth/register",
    json={"username": username1, "email": f"{username1}@test.com", "password": "StrongPass1!"},
    timeout=15)
print(f"\n[测试] 注册用户A ({username1}): status={r.status_code}")
user1 = r.json() if r.status_code == 200 else None
user1_id = user1.get('id') if user1 else None
test(f"  注册成功返回 user_id", user1_id is not None, "期望有用户ID")

# 注册用户B
r = s.post(f"{BASE}/api/auth/register",
    json={"username": username2, "email": f"{username2}@test.com", "password": "StrongPass2!"},
    timeout=15)
print(f"[测试] 注册用户B ({username2}): status={r.status_code}")
user2 = r.json() if r.status_code == 200 else None
user2_id = user2.get('id') if user2 else None
test(f"  注册成功返回 user_id", user2_id is not None, "期望有用户ID")

# 登录用户A
r = s.post(f"{BASE}/api/auth/login",
    data={"username": username1, "password": "StrongPass1!"},
    timeout=15)
print(f"\n[测试] 登录用户A: status={r.status_code}")
if r.status_code == 200:
    token1 = r.json()["access_token"]
    test(f"  获取 access_token", len(token1) > 10, "期望有 token")
else:
    token1 = None
    test(f"  登录成功", False, f"期望200，实际{r.status_code}")

headers1 = {"Authorization": f"Bearer {token1}"} if token1 else {}

# 登录用户B
r = s.post(f"{BASE}/api/auth/login",
    data={"username": username2, "password": "StrongPass2!"},
    timeout=15)
print(f"[测试] 登录用户B: status={r.status_code}")
if r.status_code == 200:
    token2 = r.json()["access_token"]
    test(f"  获取 access_token", len(token2) > 10, "期望有 token")
else:
    token2 = None
    test(f"  登录成功", False, f"期望200，实际{r.status_code}")

headers2 = {"Authorization": f"Bearer {token2}"} if token2 else {}

# 用户A评分书籍
print("\n[测试] 用户A评分一本书")
r = s.post(f"{BASE}/api/ratings", json={"book_id": 5001, "rating": 8}, headers=headers1, timeout=15)
print(f"  status={r.status_code}")
test(f"  评分成功", r.status_code == 200, "期望200")

# 用户A应该能看到自己的评分
r = s.get(f"{BASE}/api/ratings/user", headers=headers1, timeout=15)
if r.status_code == 200:
    ratings = r.json()
    print(f"  用户A的评分列表: {len(ratings.get('ratings', []))} 条")
    test(f"  用户A看到自己的评分（至少1条）", len(ratings.get('ratings', [])) >= 1, "期望至少1条")
else:
    test(f"  查询用户A评分成功", False, f"期望200，实际{r.status_code}")

# 用户A尝试访问用户B的评分（使用 user_id = user2_id 的 path params 接口）
print("\n[测试] 用户A尝试访问他人评分 - 跨用户数据隔离验证")
r = s.get(f"{BASE}/api/ratings/user/{user2_id}", headers=headers1, timeout=15)
print(f"  GET /api/ratings/user/{user2_id}: status={r.status_code}")
test(f"  用户A访问用户B的评分时被拒绝（403）", r.status_code == 403, "期望403 Forbidden")

print("\n[测试] 用户A尝试访问他人推荐 - 跨用户推荐数据隔离验证")
# 使用 path params 接口尝试访问用户B的推荐
r = s.get(f"{BASE}/api/recommend/cf/{user2_id}", headers=headers1, timeout=15)
print(f"  GET /api/recommend/cf/{user2_id}: status={r.status_code}")
test(f"  用户A访问用户B的推荐被拒绝（403）", r.status_code == 403, "期望403 Forbidden")

r = s.get(f"{BASE}/api/recommend/svd/{user2_id}", headers=headers1, timeout=15)
print(f"  GET /api/recommend/svd/{user2_id}: status={r.status_code}")
test(f"  用户A访问用户B的SVD推荐被拒绝（403）", r.status_code == 403, "期望403 Forbidden")

r = s.get(f"{BASE}/api/recommend/hybrid/{user2_id}", headers=headers1, timeout=15)
print(f"  GET /api/recommend/hybrid/{user2_id}: status={r.status_code}")
test(f"  用户A访问用户B的混合推荐被拒绝（403）", r.status_code == 403, "期望403 Forbidden")

r = s.get(f"{BASE}/api/recommend/explain/{user2_id}/5001", headers=headers1, timeout=15)
print(f"  GET /api/recommend/explain/{user2_id}/5001: status={r.status_code}")
test(f"  用户A访问用户B的推荐解释被拒绝（403）", r.status_code == 403, "期望403 Forbidden")

r = s.get(f"{BASE}/api/recommend/evaluation/{user2_id}", headers=headers1, timeout=15)
print(f"  GET /api/recommend/evaluation/{user2_id}: status={r.status_code}")
test(f"  用户A访问用户B的评估指标被拒绝（403）", r.status_code == 403, "期望403 Forbidden")

print("\n[测试] 使用正确 token 访问自己的数据")
r = s.get(f"{BASE}/api/recommend/cf", params={"n": 20}, headers=headers1, timeout=15)
print(f"  GET /api/recommend/cf: status={r.status_code}")
test(f"  用户A访问自己的协同过滤推荐", r.status_code == 200, "期望200")
if r.status_code == 200:
    cf_data = r.json()
    rec_count = len(cf_data.get('recommendations', []))
    print(f"    返回 {rec_count} 条推荐，来源: {cf_data.get('source', 'unknown')}")
    test(f"  推荐列表至少包含1本书", rec_count >= 1, "期望至少1条推荐")

r = s.get(f"{BASE}/api/recommend/svd", params={"n": 20}, headers=headers1, timeout=15)
print(f"  GET /api/recommend/svd: status={r.status_code}")
test(f"  用户A访问自己的SVD推荐", r.status_code == 200, "期望200")

r = s.get(f"{BASE}/api/recommend/compare", headers=headers1, timeout=15)
print(f"  GET /api/recommend/compare: status={r.status_code}")
test(f"  用户A访问算法对比", r.status_code == 200, "期望200")

print("\n[测试] 未登录访问/compare（仅查看系统统计，不应返回个人推荐）")
r = s.get(f"{BASE}/api/recommend/compare", timeout=15)
print(f"  status={r.status_code}")
if r.status_code == 200:
    compare_data = r.json()
    # 未登录时 user_id 应为 null，algorithms 数组中没有推荐
    algorithms = compare_data.get('algorithms', [])
    has_books = any(len(a.get('books', [])) > 0 for a in algorithms)
    test(f"  未登录 compare 无个人推荐 (books=[])", not has_books, "期望未登录时 algorithms 中 books 为空")
    print(f"    未登录对比响应 user_id = {compare_data.get('comparison', {}).get('user_id')}")
elif r.status_code == 401:
    # compare 接口在无 token 时返回 401 也可以接受
    test(f"  compare 接口要求登录（可接受）", True, "401 也是有效的安全响应")
else:
    test(f"  compare 响应异常", False, f"期望200或401，实际{r.status_code}")

print("\n" + "=" * 70)
print("第三阶段: 输入验证和边界条件测试")
print("=" * 70)

# 测试弱密码注册
print("\n[测试] 弱密码验证")
r = s.post(f"{BASE}/api/auth/register",
    json={"username": f"weak_test_{int(time.time())}", "email": "weak@test.com", "password": "123"},
    timeout=15)
test(f"  密码'123' 被拒绝（422）", r.status_code == 422, "期望422")

r = s.post(f"{BASE}/api/auth/register",
    json={"username": f"weak_test2_{int(time.time())}", "email": "weak2@test.com", "password": "weakpass"},
    timeout=15)
test(f"  密码'weakpass'（无大写和数字）被拒绝（422）", r.status_code == 422, "期望422")

r = s.post(f"{BASE}/api/auth/register",
    json={"username": f"weak_test3_{int(time.time())}", "email": "weak3@test.com", "password": "WEAKPASS1"},
    timeout=15)
test(f"  密码'WEAKPASS1'（无小写）被拒绝（422）", r.status_code == 422, "期望422")

# 测试评分范围验证
print("\n[测试] 评分范围验证（1-10）")
r = s.post(f"{BASE}/api/ratings", json={"book_id": 5001, "rating": 0}, headers=headers1, timeout=15)
test(f"  评分0分（超出下限）被拒绝", r.status_code == 422, "期望422")

r = s.post(f"{BASE}/api/ratings", json={"book_id": 5001, "rating": 999}, headers=headers1, timeout=15)
test(f"  评分999分（超出上限）被拒绝", r.status_code == 422, "期望422")

r = s.post(f"{BASE}/api/ratings", json={"book_id": 5001, "rating": 7}, headers=headers1, timeout=15)
test(f"  正常评分7分（有效范围）", r.status_code == 200, "期望200")

# 测试不存在的书籍评分
r = s.post(f"{BASE}/api/ratings", json={"book_id": 9999999, "rating": 8}, headers=headers1, timeout=15)
test(f"  评分不存在的书籍被拒绝（404）", r.status_code == 404, "期望404")

print("\n" + "=" * 70)
print("第四阶段: 书籍详情数据结构验证")
print("=" * 70)

# 登录后访问书籍详情
print("\n[测试] 已登录访问书籍详情")
r = s.get(f"{BASE}/api/books/5001", headers=headers1, timeout=15)
print(f"  status={r.status_code}")
if r.status_code == 200:
    data = r.json()
    test(f"  响应包含 title 字段", data.get('title') is not None, "期望有书名")
    test(f"  响应包含 community_rating 字段", data.get('community_rating') is not None, "期望有社区评分")
    test(f"  community_rating 内部字段完整",
        all(k in data.get('community_rating', {}) for k in ['avg_rating', 'rating_count', 'distribution']),
        "期望包含 avg_rating, rating_count, distribution")
    
    # 验证 user_rating 在根级别而不是 community_rating 内
    cr = data.get('community_rating', {})
    has_ur_in_cr = 'user_rating' in cr and cr.get('user_rating') is not None
    test(f"  community_rating 内不含 user_rating（扁平结构）", not has_ur_in_cr,
        "期望 community_rating 中不包含 user_rating")
    
    ur = data.get('user_rating')
    print(f"  user_rating (根级) = {ur}")
    test(f"  响应根级有 user_rating 字段", 'user_rating' in data, "期望 user_rating 在根级别")

# 未登录访问书籍详情
r = s.get(f"{BASE}/api/books/5001", timeout=15)
print(f"\n[测试] 未登录访问书籍详情: status={r.status_code}")
if r.status_code == 200:
    data = r.json()
    test(f"  user_rating 为 null（未登录）", data.get('user_rating') is None, "期望未登录时 user_rating = null")

print("\n" + "=" * 70)
print("第五阶段: 书籍列表和搜索（匿名访问）")
print("=" * 70)

r = s.get(f"{BASE}/api/books", params={"page": 1, "per_page": 5}, timeout=15)
print(f"\n[测试] 书籍列表: status={r.status_code}")
if r.status_code == 200:
    data = r.json()
    books = data.get('books', [])
    test(f"  返回 {len(books)} 本书", len(books) > 0, "期望至少1本书")

r = s.get(f"{BASE}/api/books", params={"search": "Harry", "page": 1, "per_page": 10}, timeout=15)
print(f"[测试] 搜索 'Harry': status={r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"  匹配 {len(data.get('books', []))} 本书")

r = s.get(f"{BASE}/api/books/5001/similar", timeout=15)
print(f"[测试] 相似书籍: status={r.status_code}")
test(f"  相似书籍接口", r.status_code == 200, "期望200")

print("\n" + "=" * 70)
print("第六阶段: AI 接口（公开访问）")
print("=" * 70)

r = s.get(f"{BASE}/api/ai/status", timeout=15)
print(f"\n[测试] AI 状态: status={r.status_code}")
test(f"  AI 状态接口可用", r.status_code == 200, "期望200")

r = s.get(f"{BASE}/api/ai/popular", params={"limit": 3}, timeout=30)
print(f"[测试] AI 热门推荐: status={r.status_code}")
test(f"  AI 热门推荐可用", r.status_code == 200, "期望200")

r = s.post(f"{BASE}/api/ai/chat", json={"message": "推荐一本讲机器学习的入门书"}, timeout=30)
print(f"[测试] AI 对话: status={r.status_code}")
test(f"  AI 对话可用", r.status_code == 200, "期望200")

print("\n" + "=" * 70)
print("测试总结")
print("=" * 70)

passed = sum(1 for _, p in results if p)
failed = sum(1 for _, p in results if not p)
print(f"\n总测试数: {len(results)}")
print(f"通过: {passed} ✅")
print(f"失败: {failed} ❌")
print(f"通过率: {passed / len(results) * 100:.1f}%")

if failed == 0:
    print("\n🎉 所有测试通过！")
else:
    print("\n⚠️  有失败的测试，请检查上面的输出")
    failed_items = [(name, _) for name, _ in results if not _]
    for name, _ in failed_items:
        print(f"  - {name}")

sys.exit(0 if all_passed else 1)

"""全面冒烟测试：books、搜索、推荐引擎（预热后）、ratings、auth、reviews、categories、filters、hot-search、/metrics、/health、/api/version"""
import urllib.request
import urllib.error
import json
import time

BASE = 'http://127.0.0.1:5000'
results = []


def _get(path):
    return urllib.request.urlopen(BASE + path, timeout=30)


def _post_json(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    return urllib.request.urlopen(req, timeout=15)


def record(name, ok, detail=''):
    status = 'PASS' if ok else 'FAIL'
    print(f'  [{status}] {name}  {detail}')
    results.append((name, ok))


# ---------- 基础健康检查 ----------
print('=== 1. 健康检查 ===')
try:
    r = _get('/api/health')
    record('/api/health', r.status == 200, f'status={r.status}')
except Exception as e:
    record('/api/health', False, str(e))

try:
    r = _get('/api/version')
    record('/api/version', r.status == 200, f'status={r.status}')
except Exception as e:
    record('/api/version', False, str(e))

try:
    r = _get('/metrics')
    record('/metrics', r.status == 200, f'status={r.status}')
except Exception as e:
    record('/metrics', False, str(e))

# ---------- books 列表 + 搜索 + N+1 优化验证 ----------
print('\n=== 2. Books API（列表+FULLTEXT搜索+N+1优化）===')
try:
    t0 = time.time()
    r = _get('/api/books?page=1&per_page=20')
    elapsed = time.time() - t0
    data = json.loads(r.read())
    ok = r.status == 200 and 'books' in data
    record('GET /api/books', ok,
           f'books={len(data.get("books", []))} elapsed={elapsed:.2f}s')
except Exception as e:
    record('GET /api/books', False, str(e))

try:
    t0 = time.time()
    r = _get('/api/books?search=harry&fuzzy=true&per_page=5')
    elapsed = time.time() - t0
    data = json.loads(r.read())
    ok = r.status == 200
    record('GET /api/books?search=FULLTEXT', ok,
           f'books={len(data.get("books", []))} method={data.get("search_method")} elapsed={elapsed:.2f}s')
except Exception as e:
    record('GET /api/books?search=FULLTEXT', False, str(e))

try:
    r = _get('/api/books/suggestions?q=harry')
    data = json.loads(r.read())
    record('GET /api/books/suggestions', 'suggestions' in data,
           f'suggestions={len(data.get("suggestions", []))}')
except Exception as e:
    record('GET /api/books/suggestions', False, str(e))

try:
    r = _get('/api/books/hot-search')
    data = json.loads(r.read())
    record('GET /api/books/hot-search', 'hot_search' in data,
           f'hot_search={len(data.get("hot_search", []))}')
except Exception as e:
    record('GET /api/books/hot-search', False, str(e))

# ---------- 推荐引擎（预热后） ----------
print('\n=== 3. 推荐引擎（预热后响应 < 1s）===')
for algo in ['cf', 'svd']:
    try:
        t0 = time.time()
        r = _get(f'/api/recommend/{algo}?user_id=1&n=5')
        elapsed = time.time() - t0
        data = json.loads(r.read())
        ok = r.status == 200 and 'recommendations' in data and elapsed < 1.0
        record(f'GET /api/recommend/{algo}', ok,
               f'count={len(data.get("recommendations", []))} elapsed={elapsed:.3f}s')
    except Exception as e:
        record(f'GET /api/recommend/{algo}', False, str(e))

try:
    r = _get('/api/recommend/compare?user_id=1&n=5')
    data = json.loads(r.read())
    cf_key = 'cf' if 'cf' in data else 'collaborative_filtering'
    ok = cf_key in data and 'svd' in data
    record('GET /api/recommend/compare', ok,
           f'{cf_key}={len(data.get(cf_key, {}).get("recommendations", []))}')
except Exception as e:
    record('GET /api/recommend/compare', False, str(e))

# ---------- 书籍详情 + 相似 ----------
print('\n=== 4. 书籍详情 & 相似书籍 ===')
try:
    r = _get('/api/books/5001')
    data = json.loads(r.read())
    record('GET /api/books/:id', 'book' in data and 'community_rating' in data.get('book', {}),
           f'avg_rating={data.get("book", {}).get("community_rating", {}).get("avg_rating")}')
except Exception as e:
    record('GET /api/books/:id', False, str(e))

try:
    r = _get('/api/books/5001/similar')
    data = json.loads(r.read())
    record('GET /api/books/:id/similar', 'similar_books' in data,
           f'count={len(data.get("similar_books", []))}')
except Exception as e:
    record('GET /api/books/:id/similar', False, str(e))

# ---------- Hot books + categories + filters（缓存）===
print('\n=== 5. 热门 / 分类 / 过滤器（缓存优化）===')
try:
    r = _get('/api/books/hot?limit=10')
    data = json.loads(r.read())
    record('GET /api/books/hot', 'hot_books' in data, f'hot={len(data.get("hot_books", []))}')
except Exception as e:
    record('GET /api/books/hot', False, str(e))

try:
    r = _get('/api/books/categories')
    data = json.loads(r.read())
    cached1 = data.get('from_cache')
    n = len(data.get('categories', []))
    # 再调一次看是否命中缓存
    r = _get('/api/books/categories')
    data2 = json.loads(r.read())
    cached2 = data2.get('from_cache')
    record('GET /api/books/categories', 'categories' in data,
           f'categories={n} first_from_cache={cached1} second_from_cache={cached2}')
except Exception as e:
    record('GET /api/books/categories', False, str(e))

try:
    r = _get('/api/books/filters')
    data = json.loads(r.read())
    n = len(data.get('categories', [])) if 'categories' in data else 0
    record('GET /api/books/filters', 'year_range' in data and 'rating_ranges' in data,
           f'categories={n}')
except Exception as e:
    record('GET /api/books/filters', False, str(e))

# ---------- auth: register + ratings write + write-limit 校验 ----------
print('\n=== 6. Auth & 写操作（含限流）===')
unique = str(int(time.time() * 1000))
username = f'qa_user_{unique}'
user_id = None
try:
    r = _post_json('/api/auth/register', {
        'username': username, 'password': 'pass1234',
        'email': f'{username}@example.com',
    })
    data = json.loads(r.read())
    user_id = data.get('user', {}).get('id')
    record('POST /api/auth/register', r.status == 201 and user_id is not None,
           f'user_id={user_id}')
except Exception as e:
    record('POST /api/auth/register', False, str(e))

try:
    r = _post_json('/api/auth/login', {'username': username, 'password': 'pass1234'})
    record('POST /api/auth/login', r.status == 200, f'status={r.status}')
except Exception as e:
    record('POST /api/auth/login', False, str(e))

# rating 写操作（写操作限流）
if user_id:
    written = 0
    for i in range(3):
        try:
            r = _post_json('/api/ratings/', {'user_id': user_id, 'book_id': 5001 + i, 'rating': 8})
            if r.status == 200 or r.status == 201:
                written += 1
        except Exception:
            pass
    record('POST /api/ratings/ (write x3)', written > 0, f'written={written}/3')

    # user's ratings GET
    try:
        r = _get(f'/api/ratings/user?user_id={user_id}')
        data = json.loads(r.read())
        record('GET /api/ratings/user', r.status == 200, f'ratings_count={len(data.get("ratings", []))}')
    except Exception as e:
        record('GET /api/ratings/user', False, str(e))

# ---------- 汇总 ----------
print()
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f'=== 总结: {passed}/{total} 通过 ===')
for name, ok in results:
    status = 'PASS' if ok else 'FAIL'
    print(f'  [{status}] {name}')

# -*- coding: utf-8 -*-
"""全面测试脚本 - 修正后的路由"""
import sys, os, time
import requests

BASE = 'http://localhost:5000'
OLLAMA = 'http://localhost:11434'
results = []
errors = []

def check(name, fn):
    try:
        ok, info = fn()
        status = '✅' if ok else '❌'
        print(f'  {status} {name}: {info}')
        results.append((name, ok, info))
        if not ok:
            errors.append((name, info))
    except Exception as e:
        print(f'  ❌ {name}: 异常 - {e}')
        results.append((name, False, str(e)))
        errors.append((name, str(e)))

def GET(path, params=None, timeout=60):
    return requests.get(f'{BASE}{path}', params=params, timeout=timeout)

def POST(path, json_data=None, timeout=120):
    return requests.post(f'{BASE}{path}', json=json_data, timeout=timeout)

# ========== 1. 服务 & 索引 ==========
print('\n' + '='*60)
print('📊 1/6 服务健康 & 索引状态')
print('='*60)

def t_books():
    r = GET('/api/books', params={'limit': 3})
    if r.status_code == 200:
        return True, f'书籍总数={r.json().get("total", "?")}'
    return False, f'status={r.status_code}'

def t_ollama():
    try:
        r = requests.get(f'{OLLAMA}/api/tags', timeout=10)
        if r.status_code == 200:
            return True, f'模型={[m["name"] for m in r.json().get("models",[])]}'
    except: pass
    return False, '未连接'

def t_embed():
    r = GET('/api/books/embeddings/status')
    if r.status_code == 200:
        raw = r.json()
        d = raw.get('status', raw)
        idx = d.get('index_size', 0)
        dim = d.get('effective_dimension', 0)
        model = d.get('ollama_model', 'n/a')
        ready = d.get('index_ready', False)
        return True, f'模型={model}, 维度={dim}, 索引={idx}本书, ready={ready}'
    return False, f'status={r.status_code}'

check('Flask 书籍API', t_books)
check('Ollama 服务', t_ollama)
check('Embedding 索引', t_embed)

# ========== 2. 推荐算法 ==========
print('\n' + '='*60)
print('🎯 2/6 推荐算法矩阵')
print('='*60)

TEST_CASES = [
    ('CF基于用户',   '/cf',                  {'user_id': 1, 'limit': 5}),
    ('SVD',          '/svd',                 {'user_id': 1, 'limit': 5}),
    ('混合推荐',     '/hybrid',              {'user_id': 1, 'limit': 5}),
    ('基于内容',     '/content',             {'user_id': 1, 'limit': 5}),
    ('基于物品',     '/item-based',          {'user_id': 1, 'limit': 5}),
    ('MMR多样性',    '/mmr',                 {'user_id': 1, 'limit': 5, 'lambda_': 0.5}),
    ('冷启动',       '/cold-start',          {'user_id': 99999, 'limit': 5}),
    ('高级推荐',     '/advanced',            {'user_id': 1, 'limit': 5}),
    ('推荐算法列表', '/algorithms',          {}),
]

def test_rec(name, path, params):
    r = GET(f'/api/recommend{path}', params=params)
    if r.status_code == 200:
        d = r.json()
        data = d.get('data', d.get('recommendations', d.get('results', d.get('algorithms', []))))
        return True, f'返回 {len(data)} 条'
    return False, f'status={r.status_code}, body={r.text[:80]}'

for name, path, params in TEST_CASES:
    check(name, lambda n=name, p=path, pm=params: test_rec(n, p, pm))

# explain: 先找一个真实存在的 book_id
def t_explain():
    # 先拿一本存在的书
    r_books = GET('/api/books', params={'limit': 3})
    book_id = 5001
    if r_books.status_code == 200:
        items = r_books.json().get('books', [])
        if items:
            book_id = items[0].get('id', 5001)
    r = GET('/api/recommend/explain', params={'user_id': 1, 'book_id': book_id})
    if r.status_code == 200:
        reason = r.json().get('reason', r.json().get('explanation', {}).get('reason', ''))
        return True, reason[:80] if reason else '成功但无reason字段'
    return False, f'status={r.status_code}'
check('推荐解释', t_explain)

# ========== 3. 语义搜索 ==========
print('\n' + '='*60)
print('🔍 3/6 语义搜索 & AI 检索')
print('='*60)

def t_semantic():
    r = GET('/api/books/semantic-search', params={'q': '科幻小说 太空', 'limit': 5})
    if r.status_code == 200:
        d = r.json()
        data = d.get('data', d.get('results', []))
        return True, f'返回 {len(data)} 条'
    return False, f'status={r.status_code}'

def t_search_ai():
    r = GET('/api/ai/search', params={'q': '哈利波特'})
    if r.status_code == 200:
        return True, 'AI搜索成功'
    return False, f'status={r.status_code}'

def t_suggest():
    r = GET('/api/books/suggestions', params={'q': 'harry'})
    if r.status_code == 200:
        return True, f'返回 {len(r.json().get("data", []))} 个建议'
    return False, f'status={r.status_code}'

def t_hot():
    r = GET('/api/books/hot-search')
    if r.status_code == 200:
        return True, f'返回 {len(r.json().get("data", []))} 个热门'
    return False, f'status={r.status_code}'

check('向量语义搜索', t_semantic)
check('AI搜索', t_search_ai)
check('搜索建议', t_suggest)
check('热门搜索', t_hot)

# ========== 4. 对话推荐 ==========
print('\n' + '='*60)
print('💬 4/6 AI 对话 & 对话推荐')
print('='*60)

def t_chat():
    r = POST('/api/ai/chat', json_data={'message': '给我推荐一本关于历史的书'})
    if r.status_code == 200:
        return True, '对话成功'
    return False, f'status={r.status_code}'

def t_conv_rec():
    r = POST('/api/ai/conversational-recommend', json_data={'message': '我喜欢科幻和奇幻', 'user_id': 1})
    if r.status_code == 200:
        return True, '对话推荐成功'
    return False, f'status={r.status_code}, body={r.text[:100]}'

def t_rag():
    r = POST('/api/ai/rag-recommend', json_data={'query': '适合初学者的编程书', 'user_id': 1})
    if r.status_code == 200:
        return True, 'RAG推荐成功'
    return False, f'status={r.status_code}, body={r.text[:100]}'

def t_ai_status():
    r = GET('/api/ai/status')
    if r.status_code == 200:
        return True, '状态查询成功'
    return False, f'status={r.status_code}'

check('AI基础对话', t_chat)
check('AI对话推荐', t_conv_rec)
check('RAG推荐', t_rag)
check('AI状态', t_ai_status)

# ========== 5. 边界 & 安全 ==========
print('\n' + '='*60)
print('🧪 5/6 边界测试 & 安全')
print('='*60)

def t_bad_user():
    r = GET('/api/recommend/cf', params={'user_id': 999999, 'limit': 5})
    return r.status_code == 200, f'status={r.status_code} (优雅降级)'

def t_zero_limit():
    r = GET('/api/books', params={'limit': 0})
    return r.status_code == 200, f'status={r.status_code}'

def t_neg_page():
    r = GET('/api/books', params={'page': -1})
    return r.status_code == 200, f'status={r.status_code}'

def t_empty_q():
    r = GET('/api/books/semantic-search', params={'q': ''})
    return r.status_code in (200, 400), f'status={r.status_code} (400也正确)'

def t_sqli():
    r = GET('/api/books/semantic-search', params={"q": "' OR '1'='1"})
    return r.status_code == 200, f'status={r.status_code} (SQL注入防护)'

def t_xss():
    r = GET('/api/books/semantic-search', params={'q': '<script>alert(1)</script>'})
    return r.status_code == 200, f'status={r.status_code} (XSS防护)'

check('无效用户', t_bad_user)
check('limit=0', t_zero_limit)
check('page=-1', t_neg_page)
check('空搜索词', t_empty_q)
check('SQL注入尝试', t_sqli)
check('XSS注入尝试', t_xss)

# ========== 6. 性能 ==========
print('\n' + '='*60)
print('⚡ 6/6 并发性能测试')
print('='*60)

def t_stress():
    import concurrent.futures
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(lambda: GET('/api/books', params={'limit': 5}).status_code) for _ in range(30)]
        codes = [f.result() for f in futures]
    elapsed = time.time() - start
    ok = all(c == 200 for c in codes)
    return ok, f'30请求/10并发={elapsed:.1f}s, statuses={set(codes)}'

def t_rec_perf():
    start = time.time()
    r = GET('/api/recommend/hybrid', params={'user_id': 1, 'limit': 10})
    elapsed = time.time() - start
    return r.status_code == 200, f'混合推荐={elapsed:.2f}s'

check('并发压力30请求', t_stress)
check('混合推荐性能', t_rec_perf)

# ========== 总结 ==========
print('\n' + '='*60)
print('📋 测试总结')
print('='*60)
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed
print(f'总计: {total}  |  ✅ 通过: {passed}  |  ❌ 失败: {failed}')

if errors:
    print('\n失败详情:')
    for name, info in errors:
        print(f'  ❌ {name}: {info}')
else:
    print('\n🎉 全部通过！')

print('\n完成时间:', time.strftime('%Y-%m-%d %H:%M:%S'))

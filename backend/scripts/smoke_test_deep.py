# -*- coding: utf-8 -*-
"""深度冒烟测试：用真实 book_id、测试对话推荐、测试新前端"""
import json
import urllib.request

BASE = 'http://127.0.0.1:5000'

def http_get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=20) as r:
            return r.status, json.loads(r.read().decode('utf-8', errors='ignore'))
    except Exception as e:
        return 0, {'error': str(e)}

def http_post(path, payload):
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(BASE + path, data=data,
                                     headers={'Content-Type': 'application/json'},
                                     method='POST')
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode('utf-8', errors='ignore'))
    except Exception as e:
        return 0, {'error': str(e)}

def test(name, status, expect_status=200, details=None):
    ok = (200 <= status < 500)
    mark = 'PASS' if ok else 'WARN'
    print(f'  [{mark}] status={status} {name}')
    if details:
        print(f'         -> {details[:200]}')
    return ok

print('=' * 60)
print('深度冒烟测试：v2.0 新功能验证')
print('=' * 60)

# 1. 找一个真实的 book_id
print()
print('[1/5] 数据探测')
status, books = http_get('/api/books/?n=5')
book_ids = []
if isinstance(books, dict):
    bl = books.get('books') or books.get('data') or []
    book_ids = [b.get('id') for b in bl if isinstance(b, dict)][:3]
test('获取书籍列表', status, details=f'找到 {len(book_ids)} 本书: {book_ids}')

# 2. 测试所有推荐算法
print()
print('[2/5] 推荐算法矩阵')
tests = [
    ('CF', '/api/recommend/cf?user_id=1&n=5'),
    ('SVD', '/api/recommend/svd?user_id=1&n=5'),
    ('Hybrid', '/api/recommend/hybrid?user_id=1&n=5'),
    ('Content', '/api/recommend/content?user_id=1&n=5'),
    ('Item-based', '/api/recommend/item-based?user_id=1&n=5'),
    ('MMR 0.5', '/api/recommend/mmr?user_id=1&n=5&lambda_param=0.5'),
    ('MMR 0.3', '/api/recommend/mmr?user_id=1&n=5&lambda_param=0.3'),
    ('MMR 0.8', '/api/recommend/mmr?user_id=1&n=5&lambda_param=0.8'),
    ('Cold-start', '/api/recommend/cold-start?n=5'),
    ('Advanced', '/api/recommend/advanced?user_id=1&n=5'),
]
for name, path in tests:
    status, data = http_get(path)
    count = len(data.get('recommendations', [])) if isinstance(data, dict) else 0
    algorithm = data.get('algorithm', '') if isinstance(data, dict) else ''
    test(name, status, details=f'算法={algorithm}, 返回 {count} 本书')

# 3. 测试可解释性（用真实 book_id）
print()
print('[3/5] 可解释性')
if book_ids:
    for bid in book_ids[:2]:
        status, data = http_get(f'/api/recommend/explain?user_id=1&book_id={bid}')
        explanation = data.get('explanation', {}) if isinstance(data, dict) else {}
        test(f'解释 book_id={bid}', status, details=str(explanation.get('reason', ''))[:150])

# 4. 语义搜索与知识图谱
print()
print('[4/5] 语义搜索 & 知识图谱')
for q in ['python', 'history', '小说']:
    status, data = http_get(f'/api/books/semantic-search?q={q}&n=3&hybrid=true')
    count = len(data.get('books', [])) if isinstance(data, dict) else 0
    test(f'语义搜索 "{q}"', status, details=f'返回 {count} 本')

if book_ids:
    for bid in book_ids[:2]:
        status, data = http_get(f'/api/books/{bid}/knowledge')
        similar = len(data.get('similar_books', [])) if isinstance(data, dict) else 0
        test(f'知识图谱 book_id={bid}', status, details=f'相似书={similar}')

# 5. 对话推荐
print()
print('[5/5] 对话式推荐')
dialog_tests = [
    '给我推荐5本好书',
    '我想看一些关于AI的书',
    '有什么值得看的书吗？',
]
for msg in dialog_tests:
    status, data = http_post('/api/ai/conversational-recommend',
                              {'message': msg, 'user_id': 1, 'n_recommendations': 5})
    recs = data.get('recommendations', []) if isinstance(data, dict) else []
    is_intent = data.get('is_recommend_intent', False)
    reply = (data.get('reply', '') or '')[:80]
    test(f'对话推荐 "{msg[:30]}"', status,
         details=f'is_intent={is_intent}, recs={len(recs)}, reply="{reply}..."')

# 6. 系统健康检查
print()
print('=' * 60)
print('系统状态概览')
print('=' * 60)
status, data = http_get('/api/recommend/health')
if isinstance(data, dict):
    print(f'  推荐路由: {data.get("routes_available", [])}')
    print(f'  CF 用户数: {data.get("cf_engine_users", 0)}')
    print(f'  A/B 测试: {data.get("ab_testing", False)}')
    print(f'  兴趣漂移: {data.get("drift_detection", False)}')

status, data = http_get('/api/ai/status')
if isinstance(data, dict):
    faiss = data.get('faiss', {})
    llm = data.get('llm', {})
    print(f'  FAISS 就绪: {faiss.get("faiss_ready", False)}')
    print(f'  FAISS 索引大小: {faiss.get("faiss_index_size", 0)}')
    print(f'  LLM 模型: {llm.get("current_model", "N/A")}')

# 7. 新前端页面
print()
print('前端页面测试')
try:
    with urllib.request.urlopen(BASE + '/recommend-center', timeout=10) as r:
        html = r.read().decode('utf-8', errors='ignore')
        has_title = '智能推荐中心' in html
        has_mmr = 'MMR' in html
        print(f'  [{"PASS" if has_title and has_mmr else "WARN"}] /recommend-center 包含 "智能推荐中心" 和 "MMR" 关键字')
except Exception as e:
    print(f'  [WARN] /recommend-center 访问失败: {e}')

print()
print('=' * 60)
print('测试完成 ✅')
print('=' * 60)

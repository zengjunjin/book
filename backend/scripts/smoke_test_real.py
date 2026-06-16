# -*- coding: utf-8 -*-
"""用真实存在的 ID 做深入冒烟测试"""
import json
import urllib.request

BASE = 'http://127.0.0.1:5000'

def http_get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=15) as r:
            return r.status, json.loads(r.read().decode('utf-8', errors='ignore'))
    except Exception as e:
        return 0, {'error': str(e)}

def test(name, path, expect_keys=None):
    status, data = http_get(path)
    ok = (200 <= status < 400)
    if expect_keys and isinstance(data, dict):
        for k in expect_keys:
            if k in json.dumps(data, ensure_ascii=False):
                break
        else:
            ok = ok and False
    summary = json.dumps(data, ensure_ascii=False)[:160]
    mark = 'PASS' if ok else 'WARN'
    print(f'  [{mark}] status={status:<4} {name}')
    print(f'         -> {summary}')
    return ok

print('== 真实数据测试 ==')

# 1. 先找一个有评分的 user_id
print()
print('-- 获取有效用户/图书 ID --')
status, data = http_get('/api/auth/register')  # 或者直接尝试 user_id=1
print(f'  user 1: status={status}, keys={list(data.keys())[:5] if isinstance(data, dict) else data}')

# 2. 推荐接口测试
print()
print('-- Recommend 全量测试 --')
test('cf recommend', '/api/recommend/cf?user_id=1&n=5')
test('svd recommend', '/api/recommend/svd?user_id=1&n=5')
test('hybrid recommend', '/api/recommend/hybrid?user_id=1&n=5')
test('content-based', '/api/recommend/content?user_id=1&n=5')
test('item-based cf', '/api/recommend/item-based?user_id=1&n=5')
test('mmr rerank', '/api/recommend/mmr?user_id=1&n=5&lambda_param=0.5')
test('cold-start', '/api/recommend/cold-start?n=5')
test('advanced', '/api/recommend/advanced?user_id=1&n=5')

# 3. 知识图谱测试（用一个真实 book_id）
print()
print('-- Books 测试 --')
test('books list', '/api/books/?n=3')
# 从 books list 中取一个 ID
status, books_data = http_get('/api/books/?n=3')
a_book_id = None
if isinstance(books_data, dict):
    books_list = books_data.get('books') or books_data.get('data') or []
    if isinstance(books_list, list) and books_list:
        first = books_list[0]
        a_book_id = first.get('id') if isinstance(first, dict) else None
if a_book_id:
    test(f'knowledge graph (id={a_book_id})', f'/api/books/{a_book_id}/knowledge')
    test(f'similar (id={a_book_id})', f'/api/books/{a_book_id}/similar?n=5')
    test(f'explain (book_id={a_book_id})', f'/api/recommend/explain?user_id=1&book_id={a_book_id}')
else:
    print('  WARN: could not find a real book_id, skipping knowledge/explain')

# 4. 用户画像测试
print()
print('-- Auth 测试 --')
test('profile (user 1)', '/api/auth/profile?user_id=1')

# 5. AI 能力测试
print()
print('-- AI 测试 --')
test('ai status', '/api/ai/status')
test('ai recommend', '/api/ai/recommend?user_id=1&n=3')
test('rag recommend', '/api/ai/rag-recommend?n=3&query=machine%20learning')

print()
print('== 测试完成 ==')

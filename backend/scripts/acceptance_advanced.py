"""扩展冒烟测试：测试 T2/T5/T6 的高级功能"""
import urllib.request
import json
import time
import sys

BASE = 'http://127.0.0.1:5000'


def get(path):
    r = urllib.request.urlopen(BASE + path)
    return r.status, json.loads(r.read()), dict(r.headers)


def post(path, payload):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={'Content-Type': 'application/json'},
                                 method='POST')
    r = urllib.request.urlopen(req)
    return r.status, json.loads(r.read()), dict(r.headers)


fail = []


def expect(name, cond, detail=''):
    if cond:
        print(f'  [PASS] {name} {detail}')
    else:
        print(f'  [FAIL] {name} {detail}')
        fail.append(name)


print('=== T2: /api/recommend/advanced (4路召回+精排) ===')
t0 = time.time()
status, body, _ = get('/api/recommend/advanced?user_id=100&n=5')
elapsed = time.time() - t0
expect('advanced: status==200', status == 200, f'status={status}')
expect('advanced: algorithm', body.get('algorithm') == 'advanced_4stage', f'alg={body.get("algorithm")}')
expect('advanced: count>=1', body.get('count', 0) >= 1, f'count={body.get("count")}')
expect('advanced: 响应<3s', elapsed < 3.0, f'elapsed={elapsed:.2f}s')
print(f'  channel_hits={body.get("channel_hits")}')
for rec in body.get('recommendations', [])[:2]:
    print(f'    - {rec.get("title")[:30]} final={rec.get("final_score")} sources={rec.get("sources")}')

print()
print('=== T5: /api/home (首页聚合 + Cache-Control/ETag) ===')
t0 = time.time()
status, body, headers = get('/api/home')
expect('home: status==200', status == 200, f'status={status}')
expect('home: hot_search >=1', len(body.get('hot_search', [])) >= 1, f'hs={len(body.get("hot_search",[]))}')
expect('home: hot_books >=1', len(body.get('hot_books', [])) >= 1, f'hb={len(body.get("hot_books",[]))}')
expect('home: Cache-Control set', 'Cache-Control' in headers, f'CC={headers.get("Cache-Control")}')
expect('home: ETag set', 'ETag' in headers, f'ETag={headers.get("ETag")}')
print(f'  elapsed={time.time()-t0:.3f}s  Cache-Control={headers.get("Cache-Control")}  ETag={headers.get("ETag")}')

print()
print('=== T5: /ai/rag-recommend (检索+生成+引用溯源) ===')
t0 = time.time()
status, body, _ = post('/api/ai/rag-recommend', {'user_id': 200, 'top_k': 3, 'query': 'science fiction'})
elapsed = time.time() - t0
expect('rag: status==200', status == 200, f'status={status}')
expect('rag: recs>=1', len(body.get('recommendations', [])) >= 1, f'recs={len(body.get("recommendations",[]))}')
expect('rag: sources>=1', len(body.get('sources', [])) >= 1, f'sources={len(body.get("sources",[]))}')
expect('rag: 响应<60s', elapsed < 60.0, f'elapsed={elapsed:.2f}s')
print(f'  candidates_retrieved={body.get("candidates_retrieved")}')
for rec in body.get('recommendations', [])[:3]:
    print(f'    - book_id={rec.get("book_id")} score={rec.get("score")}: {rec.get("title","")[:40]}')
    if rec.get('reason'):
        print(f'      {rec.get("reason","")[:80]}')

print()
print('=== T1: /api/auth/register + login (JWT) ===')
username = 'smoke_user_' + str(int(time.time()))
status, body, _ = post('/api/auth/register', {'username': username, 'password': 'test12345'})
expect('register status in [200,201]', status in (200, 201), f'status={status}')
if status == 200:
    expect('register has access_token', 'access_token' in body, f'keys={list(body.keys())[:4]}')
status, body, _ = post('/api/auth/login', {'username': username, 'password': 'test12345'})
expect('login status==200', status == 200, f'status={status}')

print()
print('=== T6: /api/recommend/health (独立推荐服务) ===')
status, body, _ = get('/api/recommend/health')
expect('recommend health status==200', status == 200, f'status={status}')
expect('prewarm_done', body.get('prewarm_done') is True, f'prewarm_done={body.get("prewarm_done")}')

print()
print(f'=== 总结: {15-len(fail)}/15 通过 ===')
for f in fail:
    print(f'  [FAIL] {f}')
if not fail:
    print('  ALL PASS ✓')
    sys.exit(0)
sys.exit(1)

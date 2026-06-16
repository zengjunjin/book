# -*- coding: utf-8 -*-
"""冒烟测试：新推荐算法 + AI 对话 + SSE 流式输出"""
import sys, os, time, json, urllib.request, urllib.error

BASE = 'http://127.0.0.1:5000'

def get(path):
    req = urllib.request.Request(BASE + path, method='GET')
    start = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        elapsed = round((time.time() - start) * 1000)
        print(f'  [{resp.status} {elapsed}ms] {path}')
        return data
    except urllib.error.HTTPError as e:
        print(f'  [HTTP {e.code}] {path}: {e}')
        return None
    except Exception as e:
        print(f'  [ERR] {path}: {e}')
        return None

def post(path, body):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    start = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        elapsed = round((time.time() - start) * 1000)
        print(f'  [{resp.status} {elapsed}ms] {path}')
        return data
    except urllib.error.HTTPError as e:
        print(f'  [HTTP {e.code}] {path}: {e}')
        return None
    except Exception as e:
        print(f'  [ERR] {path}: {e}')
        return None

def main():
    print('=== 验证服务可用性 ===')
    ok = get('/api/health')
    if not ok:
        print('服务未启动，结束测试')
        sys.exit(1)
    print()

    print('=== 新推荐算法接口 ===')
    get('/api/recommend/content?user_id=8&n=5')
    get('/api/recommend/item-based?user_id=8&n=5')
    get('/api/recommend/mmr?user_id=8&n=5&lambda_param=0.5')
    get('/api/recommend/cold-start?user_id=0&n=5&explore_ratio=0.2')
    get('/api/recommend/explain?user_id=8&book_id=1')
    print()

    print('=== AI 对话与理由生成 ===')
    chat = post('/api/ai/chat-recommend', {'user_id': 8, 'message': '推荐几本关于科幻和历史的书'})
    if chat:
        print(f'  intent: {chat.get("intent")}, recs: {len(chat.get("recommendations", []))}, llm: {chat.get("llm_used")}')
    reasons = post('/api/ai/generate-reasons', {
        'user_id': 8,
        'books': [{'book_id': 1}, {'book_id': 2}, {'book_id': 3}],
        'sources': ['content_based', 'cf']
    })
    if reasons:
        print(f'  generated reasons: {len(reasons.get("reasons", {}))}, llm_used: {reasons.get("llm_used")}')
    print()

    print('=== SSE 流式推荐（取前 3 个事件） ===')
    try:
        req = urllib.request.Request(BASE + '/api/ai/stream-recommend?user_id=8&n=3', method='GET')
        resp = urllib.request.urlopen(req, timeout=20)
        events = []
        chunk = b''
        while True:
            line = resp.readline()
            if not line:
                break
            chunk += line
            if chunk.endswith(b'\n\n'):
                text = chunk.decode('utf-8', errors='replace').strip()
                if text:
                    events.append(text[:180])
                    if len(events) >= 3:
                        break
                chunk = b''
        print(f'  received {len(events)} SSE events:')
        for e in events:
            print(f'    {e}')
    except Exception as ex:
        print(f'  SSE skipped: {ex}')
    print()

    print('=== 已有接口一致性验证 ===')
    get('/api/recommend/cf?user_id=8&n=5')
    get('/api/recommend/svd?user_id=8&n=5')
    get('/api/recommend/advanced?user_id=8&n=5')
    print()

    print('=== 搜索与用户画像相关接口 ===')
    get('/api/books/search?q=science+fiction&limit=3')
    get('/api/user/profile?user_id=8')
    get('/api/user/interest?user_id=8')
    print()

    print('=== OK: 核心端到端测试完成 ===')

if __name__ == '__main__':
    main()

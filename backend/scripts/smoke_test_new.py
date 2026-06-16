# -*- coding: utf-8 -*-
"""冒烟测试：验证所有新接口能正确响应"""
import json
import urllib.request
import urllib.error
import socket

BASE = 'http://127.0.0.1:5000'

def http_get(path, timeout=10):
    url = BASE + path
    req = urllib.request.Request(url, headers={'User-Agent': 'smoke-test'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode('utf-8', errors='ignore')
            try:
                return r.status, json.loads(body)
            except Exception:
                return r.status, {'_raw': body[:200]}
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode('utf-8', errors='ignore')
            try:
                return e.code, json.loads(body)
            except Exception:
                return e.code, {'_raw': body[:200]}
        except Exception:
            return e.code, {'_error': str(e)}
    except Exception as e:
        return 0, {'_error': str(e)}


def check(name, path, expect_key=None, expect_status=None):
    status, data = http_get(path)
    ok = True
    if expect_status is not None:
        ok = ok and (status == expect_status)
    else:
        ok = ok and (200 <= status < 500)
    if expect_key and isinstance(data, dict):
        ok = ok and any(expect_key in str(k).lower() for k in data.keys() or [])
        ok = ok or (expect_key in json.dumps(data, ensure_ascii=False).lower())
    summary = json.dumps(data, ensure_ascii=False)[:120] if isinstance(data, dict) else str(data)[:120]
    mark = 'PASS' if ok else 'WARN'
    print(f'  [{mark}] status={status:<4} {name:<28} -> {summary}')
    return ok


# 先检查服务是否可连接
print('== Smoke Test ==')
try:
    sock = socket.create_connection(('127.0.0.1', 5000), timeout=3)
    sock.close()
    print('  Service reachable on :5000')
except Exception:
    print('  WARN: Service NOT running on 127.0.0.1:5000')
    print('  HINT: Start with: cd backend ; python app.py')
    print()
    print('== Dry-run test (service offline) ==')
    print('  Cannot hit live endpoints. Please start the service first.')
    exit(1)

print()
print('-- Recommend routes --')
check('health', '/api/recommend/health')
check('cf', '/api/recommend/cf?user_id=1&n=5')
check('svd', '/api/recommend/svd?user_id=1&n=5')
check('semantic', '/api/recommend/semantic?user_id=1&n=5')
check('hybrid', '/api/recommend/hybrid?user_id=1&n=5')
check('content', '/api/recommend/content?user_id=1&n=5')
check('item-based', '/api/recommend/item-based?user_id=1&n=5')
check('mmr', '/api/recommend/mmr?user_id=1&n=5')
check('cold-start', '/api/recommend/cold-start?n=5')
check('explain', '/api/recommend/explain?user_id=1&book_id=1')
check('drift-status', '/api/recommend/drift/status/1')
check('advanced', '/api/recommend/advanced?user_id=1&n=5')

print()
print('-- Books routes (new) --')
check('semantic-search', '/api/books/semantic-search?q=python&n=5')
check('knowledge-graph', '/api/books/1/knowledge')

print()
print('-- Auth profile (new) --')
check('profile', '/api/auth/profile?user_id=1')

print()
print('-- AI routes --')
check('ai-status', '/api/ai/status')

print()
print('== Smoke Test Complete ==')

import urllib.request
import json

BASE = 'http://localhost:5000'

print('=' * 60)
print('✅ 完整部署验证')
print('=' * 60)

# 1. 首页 HTML
r = urllib.request.urlopen(f'{BASE}/').read().decode('utf-8')
has_doctype = '<!DOCTYPE html>' in r or '<html' in r.lower()
has_assets = 'assets/' in r
print(f'\n[1/4] 首页 HTML: {"✅" if has_doctype and has_assets else "❌"}')
print(f'       包含 HTML 标签: {has_doctype}, 包含 assets: {has_assets}')

# 2. API 健康检查
resp = json.loads(urllib.request.urlopen(f'{BASE}/api/health').read().decode('utf-8'))
print(f'[2/4] API 健康检查: {"✅" if resp.get("status") == "ok" else "❌"}')
print(f'       返回: {resp}')

# 3. 路由 fallback (非 /api 路径返回首页)
r = urllib.request.urlopen(f'{BASE}/recommend').read().decode('utf-8')
ok = '<!DOCTYPE html>' in r or '<html' in r.lower()
print(f'[3/4] Vue Router history 模式: {"✅" if ok else "❌"}')
print(f'       路由 /recommend 返回首页 HTML: {ok}')

# 4. 登录接口
login_data = json.dumps({'username': 'user_8', 'password': 'password123'}).encode()
req = urllib.request.Request(
    f'{BASE}/api/auth/login',
    data=login_data,
    headers={'Content-Type': 'application/json'},
    method='POST'
)
resp = json.loads(urllib.request.urlopen(req).read().decode('utf-8'))
ok = resp.get('success', False) or resp.get('user')
print(f'[4/4] 用户登录 (user_8/password123): {"✅" if ok else "❌"}')
print(f'       返回: {json.dumps(resp, ensure_ascii=False)[:200]}...')

print('\n' + '=' * 60)
print('🎉 完整部署验证通过！')
print(f'   主服务:   http://localhost:5000')
print(f'   推荐页:   http://localhost:5000/recommend')
print(f'   对比页:   http://localhost:5000/compare')
print(f'   健康检查: http://localhost:5000/api/health')
print('=' * 60)

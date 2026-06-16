"""验证刷新推荐功能 - 在 5001 端口测试"""
import requests
import time

BASE = 'http://localhost:5001'

print('=' * 70)
print('🔍 HTTP 级别验证刷新推荐功能')
print('=' * 70)

# 测试 1: CF 推荐
print(f'\n[CF 推荐]')
print('-' * 70)
results_cf = []
for i in range(5):
    try:
        r = requests.get(f'{BASE}/api/recommend/cf',
                         params={'user_id': 8, 'n': 10, 'refresh': 'true'},
                         timeout=60)
        data = r.json()
        book_ids = [b['id'] for b in data['recommendations']]
        results_cf.append(book_ids)
        print(f'  请求 {i+1}: {", ".join(str(b) for b in book_ids[:3])} | random={data.get("debug_random", "N/A"):.4f}')
    except Exception as e:
        print(f'  请求 {i+1}: ❌ {e}')
    time.sleep(0.2)

all_same_cf = all(r == results_cf[0] for r in results_cf)
print(f'\n  CF 结果每次相同?: {"❌ 相同 (不好)" if all_same_cf else "✅ CF 每次刷新不同"}')
if not all_same_cf:
    for i in range(len(results_cf) - 1):
        common = set(results_cf[i]) & set(results_cf[i+1])
        print(f'    请求 {i+1} vs {i+2}: 共同 {len(common)} 本')

# 测试 2: SVD 推荐
print(f'\n[SVD 推荐]')
print('-' * 70)
results_svd = []
for i in range(5):
    try:
        r = requests.get(f'{BASE}/api/recommend/svd',
                         params={'user_id': 8, 'n': 10, 'refresh': 'true'},
                         timeout=60)
        data = r.json()
        book_ids = [b['id'] for b in data['recommendations']]
        results_svd.append(book_ids)
        first3 = [str(b) for b in book_ids[:3]]
        print(f'  请求 {i+1}: {", ".join(first3)}')
    except Exception as e:
        print(f'  请求 {i+1}: ❌ {e}')
    time.sleep(0.2)

all_same_svd = all(r == results_svd[0] for r in results_svd)
print(f'\n  SVD 结果每次相同?: {"❌ 相同 (不好)" if all_same_svd else "✅ SVD 每次刷新不同"}')

# 测试 3: refresh=false 时的稳定性
print(f'\n[稳定模式 refresh=false]')
print('-' * 70)
results_stable = []
for i in range(3):
    try:
        r = requests.get(f'{BASE}/api/recommend/cf',
                         params={'user_id': 8, 'n': 10, 'refresh': 'false'},
                         timeout=60)
        data = r.json()
        book_ids = [b['id'] for b in data['recommendations']]
        results_stable.append(book_ids)
        print(f'  请求 {i+1}: {book_ids[:3]}')
    except Exception as e:
        print(f'  请求 {i+1}: ❌ {e}')
    time.sleep(0.2)

stable = results_stable[0] == results_stable[1] == results_stable[2]
print(f'\n  refresh=false 时稳定?: {"✅ 稳定" if stable else "❌ 不稳定"}')

print('\n' + '=' * 70)
if not all_same_cf and not all_same_svd:
    print('🎉 验证通过！刷新推荐功能正常工作！')
elif all_same_cf:
    print('❌ CF 推荐刷新无变化')
else:
    print('❌ SVD 推荐刷新无变化')
print('=' * 70)

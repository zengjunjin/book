"""验证刷新推荐功能 - 连续 5 次请求，看结果是否不同"""
import requests
import time
import json

BASE = 'http://localhost:5000'

print('=' * 70)
print('🔍 验证刷新推荐功能')
print('=' * 70)

# 测试 1: CF 推荐 (refresh=true - 随机模式
print(f'\n[CF 推荐]')
print('-' * 70)
results_cf = []
for i in range(5):
    try:
        r = requests.get(f'{BASE}/api/recommend/cf',
                         params={'user_id': 8, 'n': 10, 'refresh': 'true'},
                         timeout=120)
        data = r.json()
        book_ids = [b['id'] for b in data['recommendations']]
        results_cf.append(book_ids)
        first3 = [str(b) for b in book_ids[:3]]
        print(f'  请求 {i+1}: {", ".join(first3)}')
    except Exception as e:
        print(f'  请求 {i+1}: ❌ 错误 - {e}')
    time.sleep(0.1)

# 统计变化
print(f'\n  📊 CF 推荐结果变化:')
all_same_cf = all(r == results_cf[0] for r in results_cf)
if all_same_cf:
    print(f'     ❌ 所有请求返回相同结果！')
else:
    for i in range(len(results_cf) - 1):
        common = set(results_cf[i]) & set(results_cf[i+1])
        print(f'     请求 {i+1} vs {i+2}: 共同 {len(common)}/10 本')

# 测试 2: SVD 推荐
print(f'\n[SVD 推荐]')
print('-' * 70)
results_svd = []
for i in range(5):
    try:
        r = requests.get(f'{BASE}/api/recommend/svd',
                         params={'user_id': 8, 'n': 10, 'refresh': 'true'},
                         timeout=120)
        data = r.json()
        book_ids = [b['id'] for b in data['recommendations']]
        results_svd.append(book_ids)
        first3 = [str(b) for b in book_ids[:3]]
        print(f'  请求 {i+1}: {", ".join(first3)}')
    except Exception as e:
        print(f'  请求 {i+1}: ❌ 错误 - {e}')
    time.sleep(0.1)

print(f'\n  📊 SVD 推荐结果变化:')
all_same_svd = all(r == results_svd[0] for r in results_svd)
if all_same_svd:
    print(f'     ❌ 所有请求返回相同结果！')
else:
    print(f'     ✅ 每次刷新都有变化')
    for i in range(len(results_svd) - 1):
        common = set(results_svd[i]) & set(results_svd[i+1])
        print(f'     请求 {i+1} vs {i+2}: 共同 {len(common)}/10 本')

# 测试 3: refresh=false 时的稳定性
print(f'\n[稳定模式 refresh=false]')
print('-' * 70)
results_stable = []
for i in range(3):
    try:
        r = requests.get(f'{BASE}/api/recommend/cf',
                         params={'user_id': 8, 'n': 10, 'refresh': 'false'},
                         timeout=120)
        data = r.json()
        book_ids = [b['id'] for b in data['recommendations']]
        results_stable.append(book_ids)
        print(f'  请求 {i+1}: {book_ids[:3]}')
    except Exception as e:
        print(f'  请求 {i+1}: ❌ 错误 - {e}')

if results_stable[0] == results_stable[1] == results_stable[2]:
    print(f'  ✅ refresh=false 时结果稳定')
else:
    print(f'  ❌ refresh=false 时结果不稳定')

print('\n' + '=' * 70)
if not all_same_cf and not all_same_svd:
    print('🎉 验证通过！刷新推荐功能正常工作！')
    print('   - refresh=true: 每次刷新返回不同推荐')
    print('   - refresh=false: 结果稳定可复现')
elif all_same_cf:
    print('❌ CF 推荐刷新无变化！')
else:
    print('❌ SVD 推荐刷新无变化！')
print('=' * 70)

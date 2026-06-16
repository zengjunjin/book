import sys
import os
from app import create_app


def run_tests():
    app = create_app()
    client = app.test_client()
    tests = []

    def t(name, path, method='GET', expected=200, **kwargs):
        try:
            if method == 'GET':
                r = client.get(path)
            elif method == 'POST':
                r = client.post(path, **kwargs)
            else:
                r = client.open(path, method=method, **kwargs)
            ok_status = (r.status_code == expected)
            tests.append((name, ok_status, r.status_code))
            status_sym = 'OK' if ok_status else 'FAIL'
            print('  [{0}] [{1}] {2}'.format(status_sym, r.status_code, name))
        except Exception as e:
            tests.append((name, False, str(e)))
            print('  [ERR] {0}: {1}'.format(name, e))

    print('=== 健康检查测试')
    t('health check', '/api/health')
    t('version', '/api/version')

    print()
    print('=== 书籍接口测试')
    t('书籍列表', '/api/books/')
    t('热门书籍', '/api/books/hot')
    t('书籍分类', '/api/books/categories')
    t('过滤选项', '/api/books/filters')
    t('搜索建议', '/api/books/suggestions?q=harry')
    t('热门搜索', '/api/books/hot-search')

    print()
    print('=== 认证接口测试')
    t('登录: 空字段', '/api/auth/login', method='POST', json={'username': '', 'password': ''}, expected=400)
    t('注册: 空字段', '/api/auth/register', method='POST', json={'username': '', 'password': ''}, expected=400)

    print()
    print('=== 推荐接口测试')
    t('协同过滤推荐', '/api/recommend/cf?user_id=8')
    t('SVD推荐', '/api/recommend/svd?user_id=8')
    t('混合推荐', '/api/recommend/hybrid?user_id=8')
    t('算法对比', '/api/recommend/compare')

    print()
    print('=== AI 接口测试')
    t('AI状态', '/api/ai/status')

    print()
    print('=== 异步任务 API')
    t('任务健康', '/api/tasks/health')

    print()
    print('=== 404 测试')
    t('未知端点', '/api/notexist', expected=404)

    passed = sum(1 for _, ok, _ in tests if ok)
    total = len(tests)
    print()
    print('==> {0}/{1} 测试通过'.format(passed, total))
    return passed == total


if __name__ == '__main__':
    ok = run_tests()
    sys.exit(0 if ok else 1)

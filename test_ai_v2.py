"""测试 AI 内容创作助手 v2.0 - 完整功能测试"""
import requests
import json

BASE_URL = 'http://localhost:5000'

def test_api(name, method, path, data=None, show_details=False):
    print(f'\n{"="*60}')
    print(f'📡 {name}')
    print(f'   {method} {path}')
    print(f'{"="*60}')

    try:
        if method == 'GET':
            r = requests.get(f'{BASE_URL}{path}')
        else:
            r = requests.post(f'{BASE_URL}{path}', json=data)

        print(f'   HTTP Status: {r.status_code}')

        if r.status_code == 200:
            result = r.json()
            print(f'   ✅ 请求成功')

            # 美化输出关键信息
            if 'status' in result and isinstance(result['status'], dict):
                s = result['status']
                print(f'   - 运行模式: {s.get("mode")}')

            if 'review' in result:
                rev = result['review']
                print(f'   - 书名: {rev.get("book_title")}')
                print(f'   - 评分: {rev.get("rating")}')
                if show_details and rev.get("content"):
                    print(f'   - 内容预览: {rev["content"][:150]}...')

            if 'summary' in result:
                summ = result['summary']
                print(f'   - 书名: {summ.get("title")}')
                print(f'   - 一句话: {summ.get("one_line")}')
                print(f'   - 主题: {summ.get("themes", [])[:3]}')
                if show_details:
                    print(f'   - 概述: {summ.get("overview", "")[:150]}...')

            if 'analysis' in result:
                analysis = result['analysis']
                profile = analysis.get('profile', {})
                print(f'   - 书名: {profile.get("title")}')
                print(f'   - 作者: {profile.get("author")}')
                print(f'   - 平均评分: {profile.get("avg_rating")}')
                print(f'   - 评价人数: {profile.get("rating_count")}')
                print(f'   - 标签: {profile.get("tags", [])[:5]}')
                similar = analysis.get('similar_books', [])
                print(f'   - 相似书籍: {len(similar)} 本')
                if show_details and similar:
                    print(f'   - 相似书籍示例: {similar[0].get("title")}')

            if 'graph' in result:
                g = result['graph']
                print(f'   - 主题数: {len(g.get("themes", []))}')
                print(f'   - 节点数: {len(g.get("nodes", []))}')

            if 'report' in result:
                rep = result['report']
                print(f'   - 人格类型: {rep.get("personality_type")}')
                stats = rep.get('stats', {})
                print(f'   - 已读书籍: {stats.get("total_books")}')
                print(f'   - 平均评分: {stats.get("avg_rating")}')

            if 'response' in result:
                content = result['response']
                print(f'   - 响应模式: {content.get("mode")}')
                if show_details:
                    print(f'   - 内容预览: {content.get("content", "")[:150]}...')
                else:
                    print(f'   - 内容长度: {len(content.get("content", ""))} 字符')

            return True
        else:
            print(f'   ❌ 请求失败')
            print(f'   Response: {r.text[:200]}')
            return False

    except Exception as e:
        print(f'   ❌ 异常: {e}')
        return False


def main():
    print('🤖 AI 内容创作助手 v2.0 - 完整功能测试')
    print('目标: 验证所有 AI 功能接口正常工作（包括新功能）')
    print()

    results = []

    # 1. 状态检查
    results.append(test_api('1. AI 引擎状态', 'GET', '/api/ai/status'))

    # 2. 对话功能
    results.append(test_api('2. AI 对话 - 问候', 'POST', '/api/ai/chat',
        {'message': '你好，你能做什么？', 'user_id': 8, 'conversation_id': 'test_v2_1'},
        show_details=True))

    results.append(test_api('3. AI 对话 - 书评请求', 'POST', '/api/ai/chat',
        {'message': '给我推荐一些适合我的书', 'user_id': 8, 'conversation_id': 'test_v2_1'},
        show_details=False))

    # 4. 书评生成
    results.append(test_api('4. 书评生成 - book_id=5001', 'POST', '/api/ai/review/5001',
        {'style': 'personal'}, show_details=True))

    # 5. 书籍摘要（新增）
    results.append(test_api('5. 书籍摘要 - book_id=5001', 'GET', '/api/ai/summary/5001',
        show_details=True))

    # 6. 书籍搜索（新增）
    print(f'\n{"="*60}')
    print(f'📡 6. 书籍搜索 - 关键词"三体"')
    print(f'   GET /api/ai/search?q=三体')
    print(f'{"="*60}')
    try:
        r = requests.get(f'{BASE_URL}/api/ai/search?q=三体')
        print(f'   HTTP Status: {r.status_code}')
        if r.status_code == 200:
            result = r.json()
            print(f'   ✅ 请求成功')
            print(f'   - 搜索结果: {result.get("count", 0)} 本')
            if result.get('books'):
                print(f'   - 示例: 《{result[0]}》')
            results.append(True)
        else:
            print(f'   ❌ 请求失败')
            results.append(False)
    except Exception as e:
        print(f'   ❌ 异常: {e}')
        results.append(False)

    # 7. 完整分析（新增）
    results.append(test_api('7. 完整分析 - book_id=5001', 'POST', '/api/ai/analyze/5001',
        {'use_llm': False}, show_details=True))

    # 8. 知识图谱
    results.append(test_api('8. 知识图谱 - book_id=5001', 'POST', '/api/ai/knowledge/5001',
        show_details=False))

    # 9. 阅读报告
    results.append(test_api('9. 阅读报告 - user_id=8', 'POST', '/api/ai/report/8',
        show_details=True))

    # 10. 智能推荐
    results.append(test_api('10. 智能推荐 - user_id=8', 'POST', '/api/ai/recommend',
        {'user_id': 8}, show_details=True))

    # 总结
    print(f'\n\n{"="*60}')
    print('📊 测试总结')
    print(f'{"="*60}')
    passed = sum(results)
    total = len(results)
    print(f'   通过: {passed}/{total}')
    print(f'   状态: {"✅ 全部通过" if passed == total else "⚠️  部分失败"}')
    print()
    print('🎉 新增功能:')
    print('   ✓ 书籍摘要生成')
    print('   ✓ 书籍搜索')
    print('   ✓ 完整书籍分析')
    print('   ✓ 对话历史数据库持久化')
    print('   ✓ 用户偏好学习')
    print()
    print('🚀 前端页面: http://localhost:5000/#/ai')
    print()

    # Ollama 提示
    print('💡 Ollama 本地模型提示:')
    print('   如果想使用真正的 AI 模型（更智能的响应）:')
    print('   1. 访问 https://ollama.com/download 下载安装')
    print('   2. 运行: ollama pull qwen2.5:1.5b')
    print('   3. 重启后端服务器即可')
    print()

if __name__ == '__main__':
    main()

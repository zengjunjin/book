"""测试 AI 内容创作助手的所有 API 接口"""
import requests
import json

BASE_URL = 'http://localhost:5000'

def test_api(name, method, path, data=None, show_content=False):
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
                print(f'   - 推荐模型: qwen2.5, llama3.2 等')
            
            if 'review' in result:
                rev = result['review']
                print(f'   - 书名: {rev.get("book_title")}')
                print(f'   - 作者: {rev.get("author")}')
                print(f'   - 评分: {rev.get("rating")}')
                if show_content and rev.get("content"):
                    print(f'   - 内容: {rev["content"][:200]}...')
            
            if 'graph' in result:
                g = result['graph']
                print(f'   - 核心主题: {g.get("themes", [])[:4]}')
                print(f'   - 节点数: {len(g.get("nodes", []))}')
                print(f'   - 边数: {len(g.get("edges", []))}')
            
            if 'report' in result:
                rep = result['report']
                print(f'   - 人格类型: {rep.get("personality_type")}')
                stats = rep.get('stats', {})
                print(f'   - 已读书籍: {stats.get("total_books", "N/A")}')
                print(f'   - 平均评分: {stats.get("avg_rating", "N/A")}')
                if show_content and rep.get("summary"):
                    print(f'   - 摘要: {rep["summary"][:200]}...')
            
            if 'response' in result and 'content' in result['response']:
                content = result['response']['content']
                print(f'   - 响应模式: {result["response"].get("mode")}')
                if show_content:
                    print(f'   - 内容: {content[:300]}...')
                else:
                    print(f'   - 内容长度: {len(content)} 字符')
            
            if 'suggested_actions' in result:
                print(f'   - 建议操作: {len(result["suggested_actions"])} 个')
            
            return True
        else:
            print(f'   ❌ 请求失败')
            print(f'   Response: {r.text[:200]}')
            return False
            
    except Exception as e:
        print(f'   ❌ 异常: {e}')
        return False


def main():
    print('🤖 AI 内容创作助手 - API 测试')
    print('目标: 验证所有 AI 功能接口正常工作')
    print()
    
    results = []
    
    # 1. 状态检查
    results.append(test_api(
        'AI 引擎状态',
        'GET',
        '/api/ai/status'
    ))
    
    # 2. 对话功能
    results.append(test_api(
        'AI 对话 - 问候',
        'POST',
        '/api/ai/chat',
        {'message': '你好，你能做什么？', 'user_id': 8, 'conversation_id': 'test_1'},
        show_content=True
    ))
    
    results.append(test_api(
        'AI 对话 - 问推荐',
        'POST',
        '/api/ai/chat',
        {'message': '推荐一些适合我的书', 'user_id': 8, 'conversation_id': 'test_1'},
        show_content=True
    ))
    
    # 3. 书评生成
    results.append(test_api(
        '书评生成 - book_id=5001',
        'POST',
        '/api/ai/review/5001',
        {'style': 'personal'},
        show_content=True
    ))
    
    results.append(test_api(
        '书评生成 - 专业风格',
        'POST',
        '/api/ai/review/5001',
        {'style': 'professional'},
        show_content=False
    ))
    
    # 4. 知识图谱
    results.append(test_api(
        '知识图谱 - book_id=5001',
        'POST',
        '/api/ai/knowledge/5001',
        show_content=True
    ))
    
    # 5. 阅读报告
    results.append(test_api(
        '阅读报告 - user_id=8',
        'POST',
        '/api/ai/report/8',
        show_content=True
    ))
    
    # 总结
    print(f'\n\n{"="*60}')
    print('📊 测试总结')
    print(f'{"="*60}')
    passed = sum(results)
    total = len(results)
    print(f'   通过: {passed}/{total}')
    print(f'   状态: {"✅ 全部通过" if passed == total else "⚠️  部分失败"}')
    print()
    print('🚀 前端页面: http://localhost:5000/#/ai')
    print()

if __name__ == '__main__':
    main()

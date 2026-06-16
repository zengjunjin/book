import requests, json
r = requests.post('http://127.0.0.1:5000/api/ai/conversational-recommend',
    json={'message': '给我推荐5本关于AI和科技的好书', 'user_id': 1, 'n_recommendations': 5},
    timeout=40)
data = r.json()
print('意图识别:', data.get('is_recommend_intent'))
print('推荐数量:', len(data.get('recommendations', [])))
print()
for b in data.get('recommendations', []):
    print(f'  Book: {b.get("title", "?")}')
    print(f'  Author: {b.get("author", "?")}')
    print(f'  Reason: {b.get("reason", "?")}')
    print(f'  Score: {b.get("score", 0):.3f}')
    print()
print('LLM reply:')
print(data.get('reply', '')[:300])

"""检查 Ollama 是否可用"""
import requests

try:
    r = requests.get('http://localhost:11434/api/tags', timeout=3)
    if r.status_code == 200:
        data = r.json()
        models = data.get('models', [])
        print('✅ Ollama 已安装并运行!')
        print(f'已安装 {len(models)} 个模型:')
        for m in models:
            name = m.get('name', 'unknown')
            print(f'  - {name}')
    else:
        print('❌ Ollama 响应异常')
except Exception as e:
    print(f'❌ Ollama 未运行: {e}')
    print()
    print('💡 安装 Ollama 步骤:')
    print('   1. 访问 https://ollama.com/download')
    print('   2. 下载并安装 Windows 版本')
    print('   3. 打开终端，运行: ollama pull qwen2.5:1.5b')
    print('   4. 下载完成后，系统即可使用本地 AI 模型')

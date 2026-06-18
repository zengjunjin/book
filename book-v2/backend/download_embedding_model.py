"""下载 Embedding 模型"""
from sentence_transformers import SentenceTransformer

print("下载 Embedding 模型...")
model_name = "paraphrase-multilingual-MiniLM-L12-v2"
model = SentenceTransformer(model_name)
print(f"模型下载完成: {model_name}")

# 测试编码
test_text = "这是一本关于人工智能的书籍"
embedding = model.encode([test_text])
print(f"测试编码成功，向量维度: {embedding.shape}")
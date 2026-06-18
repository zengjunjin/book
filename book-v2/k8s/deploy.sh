# K8s 部署脚本
#!/bin/bash

set -e

echo "========================================"
echo "书籍推荐系统 K8s 部署脚本"
echo "========================================"

# 创建命名空间
echo "1. 创建命名空间..."
kubectl apply -f namespace.yaml

# 部署数据库和缓存
echo "2. 部署 PostgreSQL..."
kubectl apply -f postgres.yaml

echo "3. 部署 Redis..."
kubectl apply -f redis.yaml

# 等待数据库就绪
echo "4. 等待数据库就绪..."
kubectl wait --for=condition=ready pod -l app=postgres -n book-recommend --timeout=120s
kubectl wait --for=condition=ready pod -l app=redis -n book-recommend --timeout=120s

# 部署配置
echo "5. 部署配置..."
kubectl apply -f configmap.yaml

# 部署后端服务
echo "6. 部署后端服务..."
kubectl apply -f backend.yaml

# 部署 Celery Worker
echo "7. 部署 Celery Worker..."
kubectl apply -f celery.yaml

# 部署 Ingress
echo "8. 部署 Ingress..."
kubectl apply -f ingress.yaml

echo "========================================"
echo "部署完成！"
echo "========================================"
echo "检查 Pod 状态:"
kubectl get pods -n book-recommend
echo ""
echo "服务地址:"
kubectl get svc -n book-recommend

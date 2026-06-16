"""
构建前端并复制到 backend/static/ 目录
用法: python build_frontend.py
"""
import os
import sys
import shutil
import subprocess


def main():
    # 项目根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = script_dir
    frontend_dir = os.path.join(project_root, 'frontend')
    backend_dir = os.path.join(project_root, 'backend')
    dist_dir = os.path.join(frontend_dir, 'dist')
    static_dir = os.path.join(backend_dir, 'static')

    print('=' * 60)
    print('📦 构建前端 (Vue 3 + Vite)')
    print('=' * 60)

    # 1) 确保前端依赖已安装
    node_modules = os.path.join(frontend_dir, 'node_modules')
    if not os.path.isdir(node_modules):
        print('\n🔧 首次构建：正在安装前端依赖 (npm install)...')
        r = subprocess.run(['npm', 'install'], cwd=frontend_dir, shell=True)
        if r.returncode != 0:
            print('❌ 依赖安装失败，请检查 Node.js / npm 是否正确安装')
            sys.exit(1)

    # 2) 执行 npm run build
    print('\n🔨 正在构建前端 (npm run build)...')
    r = subprocess.run(['npm', 'run', 'build'], cwd=frontend_dir, shell=True)
    if r.returncode != 0:
        print('❌ 前端构建失败')
        sys.exit(1)

    if not os.path.isdir(dist_dir):
        print(f'❌ 构建产物 {dist_dir} 不存在')
        sys.exit(1)

    # 3) 清理旧的 backend/static 并复制新内容
    if os.path.isdir(static_dir):
        print(f'\n🗑  清理旧文件 {static_dir}')
        shutil.rmtree(static_dir)

    print(f'\n📋 复制构建产物到 {static_dir}')
    shutil.copytree(dist_dir, static_dir)

    # 4) 确认复制成功
    index_html = os.path.join(static_dir, 'index.html')
    asset_dir = os.path.join(static_dir, 'assets')
    ok = os.path.isfile(index_html) and os.path.isdir(asset_dir)

    print('\n' + '=' * 60)
    if ok:
        print('✅ 前端构建完成！')
        print(f'   - 入口: {index_html}')
        print(f'   - 静态资源: {asset_dir}')
        print(f'\n🚀 下一步:  cd backend && python app.py')
        print(f'   浏览器访问 http://localhost:5000')
    else:
        print('❌ 构建产物异常，请检查上面日志')
        sys.exit(1)


if __name__ == '__main__':
    main()

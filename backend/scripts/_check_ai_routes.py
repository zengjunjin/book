# -*- coding: utf-8 -*-
import re
import os

path = r'c:\Users\15116\Desktop\book\backend\ai\routes.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

pat = re.compile(r'@ai_bp\.route\([\'\"]([^\'\"]+)[\'\"]')
routes = pat.findall(content)
print('Current AI routes:', routes)
print()

keywords = ['conversational', 'stream', 'SSE', 'chat', '对话', '推荐', 'recommend']
for kw in keywords:
    hit = kw.lower() in content.lower()
    print(f'  {"✓" if hit else "✗"}  {kw}')
print()
print(f'Total lines: {len(content.splitlines())}')
print(f'File size: {os.path.getsize(path)} bytes')

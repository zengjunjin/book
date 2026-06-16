# -*- coding: utf-8 -*-
import re
import os

for name, path in [
    ('books', r'c:\Users\15116\Desktop\book\backend\routes\books.py'),
    ('auth', r'c:\Users\15116\Desktop\book\backend\routes\auth.py'),
    ('social', r'c:\Users\15116\Desktop\book\backend\routes\social.py'),
    ('recommend', r'c:\Users\15116\Desktop\book\backend\routes\recommend.py'),
]:
    print(f'===== routes/{name}.py =====')
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find route decorators - different blueprint names
    bp_map = {
        'books': r'books_bp',
        'auth': r'auth_bp',
        'social': r'social_bp',
        'recommend': r'recommend_bp',
    }
    bp = bp_map[name]
    pat = re.compile(r'@' + bp + r'\.route\([\'\"]([^\'\"]+)[\'\"]')
    routes = pat.findall(content)
    for r in routes:
        print(f'  {r}')
    print(f'  Total lines: {len(content.splitlines())}')
    print()

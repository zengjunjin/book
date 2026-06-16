import pymysql
from werkzeug.security import generate_password_hash

conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='123456', database='book_recommend', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()

# 生成一个标准密码哈希
password_hash = generate_password_hash('password123')
print(f'Password hash: {password_hash}')
print(f'Hash length: {len(password_hash)}')

# 检查当前哈希分布
cur.execute('SELECT LENGTH(password_hash) as hl, COUNT(*) as cnt FROM users GROUP BY hl')
print('\n当前哈希分布:')
for row in cur.fetchall():
    print(f'  length={row["hl"]}: {row["cnt"]} users')

# 批量更新所有用户的密码哈希
cur.execute('SELECT COUNT(*) as cnt FROM users')
total = cur.fetchone()['cnt']
print(f'\n更新 {total} 个用户的密码哈希...')

batch_size = 5000
offset = 0
updated = 0

while offset < total:
    cur.execute('SELECT id FROM users ORDER BY id LIMIT %s OFFSET %s', (batch_size, offset))
    ids = [row['id'] for row in cur.fetchall()]
    if not ids:
        break
    
    cur.executemany('UPDATE users SET password_hash = %s WHERE id = %s', [(password_hash, uid) for uid in ids])
    conn.commit()
    updated += len(ids)
    print(f'  Updated: {updated:,} / {total:,}')
    offset += batch_size

# 验证
cur.execute('SELECT LENGTH(password_hash) as hl, COUNT(*) as cnt FROM users GROUP BY hl')
print('\n更新后哈希分布:')
for row in cur.fetchall():
    print(f'  length={row["hl"]}: {row["cnt"]} users')

# 测试几个特定用户
for uid in [8, 254, 11676, 98391, 153662]:
    cur.execute('SELECT id, username, password_hash FROM users WHERE id = %s', (uid,))
    row = cur.fetchone()
    if row:
        print(f'  User {uid} ({row["username"]}): hash OK, len={len(row["password_hash"])}')

conn.close()
print('\n✓ 所有用户密码哈希已更新')
print(f'  登录: username = user_XXXXX, password = password123')

import sqlite3
import bcrypt

conn = sqlite3.connect("data/estimation.db")
c = conn.cursor()
c.execute("SELECT id, username, role, is_active, password_hash, auth_provider FROM users WHERE username='admin'")
row = c.fetchone()
if row:
    uid, uname, role, active, phash, provider = row
    print(f"id={uid}, username={uname}, role={role}, is_active={active}, provider={provider}")
    print(f"hash_exists={bool(phash)}, hash_prefix={phash[:30] if phash else None}")
    if phash:
        ok = bcrypt.checkpw(b"admin", phash.encode())
        print(f"password 'admin' valid: {ok}")
else:
    print("No admin user found")
conn.close()

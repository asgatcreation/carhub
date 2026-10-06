import sqlite3

def main():
    conn = sqlite3.connect('db.sqlite3')
    c = conn.cursor()
    print('---- django_migrations rows for users ----')
    for row in c.execute("SELECT app, name, applied FROM django_migrations WHERE app='users' ORDER BY applied"):
        print(row)
    print('\n---- users_profile table info ----')
    for row in c.execute("PRAGMA table_info('users_profile')"):
        print(row)
    print('\n---- users table info (auth user model) ----')
    for row in c.execute("PRAGMA table_info('users_customuser')"):
        print(row)
    conn.close()

if __name__ == '__main__':
    main()

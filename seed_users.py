import sqlite3

conn = sqlite3.connect("database/users.db")
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS users") # 재실행 시 중복 삽입 방지를 위해 기존 테이블 초기화

cursor.execute("""
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL
    )
""")

names = [
    "Jaewon", "Minji", "Seojun", "Hana", "Dohyun",
    "Yuna", "Jiho", "Subin", "Hyunwoo", "Chaeyoung",
    "Junho", "Areum", "Taemin", "Soyeon", "Woojin",
    "Nayeon", "Sungmin", "Eunji", "Kyungho", "Rina",
]

users = [(name, f"{name.lower()}@example.com") for name in names]

cursor.executemany("INSERT INTO users (name, email) VALUES (?, ?)", users)

conn.commit()
conn.close()

print(f"{len(users)}명의 유저 추가 완료")

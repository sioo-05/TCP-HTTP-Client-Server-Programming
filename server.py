from socket import *
import json
import sqlite3

serverPort = 8080 # 서버 포트

USERS_DB = "database/users.db"

serverSocket = socket(AF_INET, SOCK_STREAM) # 서버 소켓 생성
serverSocket.bind(('',serverPort)) # IP와 Port 지정 (모든 네트워크 인터페이스(IP)에서 8080 포트로 들어오는 연결을 받겠다.)
serverSocket.listen() # 서버 연결 대기

print('The server is ready to receive')

while True:
    connectionSocket, addr = serverSocket.accept() # 클라이언트의 연결 요청 수락 / 서버는 계속 새로운 클라이언트를 받아야 하기 때문에 항상 새 소켓을 만듦

    request = connectionSocket.recv(1024).decode()

    request_line = request.split("\r\n")[0]

    method, path, version = request_line.split()

    # 헤더 부분만 분리해서 Content-Length, Expect 값을 확인
    header_part = request.split("\r\n\r\n")[0]
    content_length = 0
    expect_continue = False
    for line in header_part.split("\r\n")[1:]: # 헤더 파트 한 줄씩
        if line.lower().startswith("content-length:"):  # content-length로 시작하면
            content_length = int(line.split(":")[1].strip()) # content_length에 값 저장
        if line.lower().startswith("expect:") and "100-continue" in line.lower():
            expect_continue = True

    # POST/PUT + Expect: 100-continue -> 바디를 받기 전에 먼저 100 Continue 응답
    if expect_continue: # 본문(body)을 보내기 전에 서버가 이 요청을 받아줄 건지 먼저 확인하고 싶다
        connectionSocket.send("HTTP/1.1 100 Continue\r\n\r\n".encode())

    # 첫 recv에 바디 일부가 이미 포함돼 있을 수 있으므로 분리하고, 부족하면 이어서 수신
    body = request.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in request else ""
    while len(body.encode()) < content_length:
        body += connectionSocket.recv(1024).decode()

    if method == "GET": # GET 요청 (db에 있는 데이터를 "가져오는" 요청)
        parts = path.strip("/").split("/")
        conn = sqlite3.connect(USERS_DB) # DB 연결
        if path == "/users":
            rows = conn.execute("SELECT id, name, email FROM users").fetchall() # 전체 행 조회
            conn.close()
            users = [{"id": r[0], "name": r[1], "email": r[2]} for r in rows]
            response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + json.dumps(users, ensure_ascii=False)
        elif len(parts) == 2 and parts[0] == "users":
            row = conn.execute("SELECT id, name, email FROM users WHERE id = ?", (int(parts[1]),)).fetchone()
            conn.close()
            if row is None: # 없으면 404
                response = "HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\n\r\n" + json.dumps({"error": "user not found"})
            else:
                user = {"id": row[0], "name": row[1], "email": row[2]}
                response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + json.dumps(user, ensure_ascii=False) # 있으면 json 객체 반환
        else:
            conn.close()
            response = "HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\n\r\n" + json.dumps({"error": "not found"})

    elif method == "HEAD":
        # HEAD: GET과 같은 헤더를 응답하되 바디는 보내지 않음
        parts = path.strip("/").split("/")
        if path == "/users":
            response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n"
        elif len(parts) == 2 and parts[0] == "users":
            conn = sqlite3.connect(USERS_DB)
            row = conn.execute("SELECT id FROM users WHERE id = ?", (int(parts[1]),)).fetchone()
            conn.close()
            if row is None:
                response = "HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\n\r\n"
            else:
                response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n"
        else:
            response = "HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\n\r\n"

    elif method == "POST": # POST 요청 (서버에 새로운 데이터를 "추가"하는 요청)
        if path == "/users":
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                data = {}

            if "name" not in data or "email" not in data:
                response = "HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\n\r\n" + json.dumps({"error": "name and email are required"})
            else:
                conn = sqlite3.connect(USERS_DB)
                cursor = conn.execute(
                    "INSERT INTO users (name, email) VALUES (?, ?)",
                    (data["name"], data["email"])
                )
                new_id = cursor.lastrowid
                conn.commit()
                conn.close()
                new_user = {"id": new_id, "name": data["name"], "email": data["email"]}
                response = "HTTP/1.1 201 Created\r\nContent-Type: application/json\r\n\r\n" + json.dumps(new_user, ensure_ascii=False)
        else:
            response = "HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\n\r\n<h1>404 Not Found</h1>"

    elif method == "PUT": # PUT 요청 (서버에 있는 데이터를 "수정"하는 요청)
        parts = path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "users":
            user_id = int(parts[1])

            conn = sqlite3.connect(USERS_DB)
            row = conn.execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,)).fetchone()

            if row is None:
                conn.close()
                response = "HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\n\r\n" + json.dumps({"error": "user not found"})
            else:
                target = {"id": row[0], "name": row[1], "email": row[2]}
                data = json.loads(body) if body else {}
                target.update({k: v for k, v in data.items() if k in ("name", "email")})

                conn.execute("UPDATE users SET name = ?, email = ? WHERE id = ?",
                             (target["name"], target["email"], user_id))
                conn.commit()
                conn.close()
                response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + json.dumps(target, ensure_ascii=False)
        else:
            response = "HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\n\r\n<h1>404 Not Found</h1>"

    elif method == "DELETE": # DELETE 요청 (db에 있는 데이터를 "삭제"하는 요청)
        parts = path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "users":
            user_id = int(parts[1]) # user_id추출

            conn = sqlite3.connect(USERS_DB)
            row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone() 
            # 이 유저가 존재하면 row에 값 들어감
            
            if row is None:
                conn.close()
                response = "HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\n\r\n" + json.dumps({"error": "user not found"})
            else:
                conn.execute("DELETE FROM users WHERE id = ?", (user_id,)) # 해당 행 삭제
                conn.commit()
                conn.close()
                response = "HTTP/1.1 204 No Content\r\n\r\n"
        else:
            response = "HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\n\r\n" + json.dumps({"error": "not found"})

    else:
        response = "HTTP/1.1 405 Method Not Allowed\r\nContent-Type: text/html\r\n\r\n<h1>405 Method Not Allowed</h1>"

    connectionSocket.send(response.encode())
    connectionSocket.close()

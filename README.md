# TCP 소켓 기반 HTTP Client/Server 구현 프로젝트

- 프로젝트명: TCP 소켓 프로그래밍을 이용한 HTTP GET/HEAD/POST/PUT/DELETE 통신 구현
- 구현 언어: Python 3.13
- 작성자: 20243149 인공지능학부 박재원
---

## 목차

1. 과제 목적
2. 개발 및 실행 환경
3. TCP 소켓 통신 개념
4. HTTP 프로토콜 개념
5. 프로그램 구조 및 파일 설명
6. 서버(server.py) 동작 과정
7. 클라이언트(client.py) 동작 과정
8. 실행 방법
9. HTTP 요청/응답 실행 결과 (Method-상태코드 케이스)
10. Wireshark 패킷 캡처 및 분석
11. 결론
부록 A. 전체 소스코드

---

## 1. 과제 목적

본 프로젝트는 TCP 기반 소켓 프로그래밍을 통해 Client-Server 구조의 통신 프로그램을 직접 구현하고, 그 위에서 HTTP 프로토콜의 요청(Request)과 응답(Response) 메시지를 애플리케이션 레벨에서 수동으로 파싱·생성함으로써 HTTP가 실제로 어떤 텍스트 포맷으로 주고받아지는지를 이해하는 것을 목표로 한다.

일반적으로 웹 프로그래밍에서는 Flask, Express, requests 라이브러리 등 이미 HTTP를 처리해주는 프레임워크를 사용하지만, 본 과제에서는 그러한 프레임워크 없이 순수 TCP 소켓(`socket` 모듈)만을 사용하여

- 클라이언트가 HTTP Request Line, Header, Body를 직접 문자열로 구성하여 전송하고
- 서버가 수신한 바이트 스트림을 파싱하여 Method/Path/Header/Body를 분리하고
- 요청에 맞는 처리를 수행한 뒤 상태 코드(Status Code)와 함께 HTTP Response를 직접 조립하여 반환한다.

이를 통해 다음을 학습한다.

- TCP 소켓의 3-way handshake, `bind`/`listen`/`accept`/`connect`/`send`/`recv`/`close`의 흐름
- HTTP 요청 메시지와 응답 메시지의 정확한 포맷 (`\r\n` 구분자, 빈 줄로 헤더/바디 구분)
- GET, HEAD, POST, PUT, DELETE 메서드의 의미 차이와 그에 따른 서버 처리 로직 차이
- 상태 코드(1xx, 2xx, 4xx 등)가 어떤 상황에서 사용되는지
- 실제 데이터베이스(SQLite)와 연동하여 요청에 따라 데이터를 조회/생성/수정/삭제하는 REST 스타일 API 서버 구현

---

## 2. 개발 및 실행 환경

| 항목 | 내용 |
|---|---|
| 운영체제 | Windows 10 |
| 언어 | Python 3.13.1 |
| 사용 모듈 | `socket` (표준 라이브러리), `json` (표준 라이브러리), `sqlite3` (표준 라이브러리) |
| 데이터베이스 | SQLite3 (`database/users.db`, 파일 기반 DB, 별도 서버 설치 불필요) |
| 통신 방식 | TCP (`SOCK_STREAM`), IPv4 (`AF_INET`) |
| 서버 주소 | `localhost` (127.0.0.1) — 1대의 PC로 실습 시 |
| 포트 번호 | 8080 |
| 실행 방식 | 서버와 클라이언트를 별도의 터미널(콘솔) 프로세스로 각각 실행 |
| 패킷 분석 도구 | Wireshark |

> 2대 이상의 PC 환경을 사용할 경우, `client.py`의 `serverName` 변수를 서버 PC의 실제 IP 주소로 변경하고, 서버 PC의 방화벽에서 8080 포트를 인바운드 허용하면 동일하게 동작한다. 본 보고서는 1대의 PC에서 `localhost`로 실습한 결과를 기준으로 작성하였다.

---

## 3. TCP 소켓 통신 개념

### 3.1 TCP의 특징

TCP(Transmission Control Protocol)는 연결 지향형(Connection-oriented), 신뢰성 있는(Reliable) 전달을 보장하는 전송 계층 프로토콜이다. UDP와 달리 데이터를 보내기 전에 반드시 **3-way handshake**를 통해 연결을 먼저 수립해야 하며, 전송 순서 보장과 오류 검출/재전송을 지원한다. HTTP는 신뢰성 있는 전달이 필요하므로 TCP 위에서 동작한다.

### 3.2 3-way Handshake

```
Client                          Server
  | ---- SYN ----------------->  |
  | <---- SYN + ACK ------------ |
  | ---- ACK ----------------->  |
  |        (연결 수립 완료)        |
```

본 프로젝트에서 `clientSocket.connect((serverName, serverPort))` 호출 시 위 3-way handshake가 OS 커널 레벨에서 자동으로 수행되며, Wireshark 캡처에서 이 과정을 실제로 확인할 수 있다 (10장 참고).

### 3.3 소켓 API 흐름

서버와 클라이언트가 사용하는 소켓 API 호출 순서는 다음과 같다.

**서버 측**

```
socket()  →  bind()  →  listen()  →  accept()  →  recv()/send()  →  close()
```

**클라이언트 측**

```
socket()  →  connect()  →  send()  →  recv()  →  close()
```

| 함수 | 역할 |
|---|---|
| `socket(AF_INET, SOCK_STREAM)` | IPv4 기반 TCP 소켓 생성 |
| `bind(('', port))` | 소켓에 로컬 IP/포트 할당 (서버 전용, `''`은 모든 인터페이스) |
| `listen()` | 클라이언트의 연결 요청을 대기하는 상태로 전환 |
| `accept()` | 대기 큐에서 연결 요청을 하나 꺼내 새로운 소켓(연결 전용 소켓)을 반환 |
| `connect((ip, port))` | 지정된 서버로 연결 요청(클라이언트 전용) |
| `send(data)` / `recv(bufsize)` | 데이터 송수신 (바이트 단위) |
| `close()` | 소켓 종료, 4-way handshake로 연결 해제 |

본 프로젝트의 서버는 `while True:` 반복문 안에서 `accept()`를 반복 호출하여 새 클라이언트를 받아들이는 **반복 서버(iterative server)** 구조이다. 다만 한 클라이언트와 맺은 연결 안에서는 다시 내부 `while True:` 루프를 돌며, 클라이언트가 소켓을 닫기 전까지(`recv()`가 빈 값을 반환하기 전까지) 같은 TCP 연결로 여러 요청을 계속 받아 처리한다. 즉 **HTTP/1.1의 기본값인 Persistent Connection(Keep-Alive)** 방식이다. 클라이언트도 프로그램 시작 시 `connect()`를 딱 한 번만 호출하고, 사용자가 `q`를 입력해 종료를 선택할 때만 `close()`를 호출한다 — 그 사이에 입력하는 여러 번호(요청)는 전부 같은 소켓 하나로 오간다.

---

## 4. HTTP 프로토콜 개념

### 4.1 요청(Request) 메시지 구조

```
<Method> <Path> <HTTP-Version>\r\n     ← Request Line
<Header-Name>: <Header-Value>\r\n      ← Header (0개 이상)
...
\r\n                                    ← 빈 줄 (헤더 종료)
<Body>                                  ← 바디 (선택적)
```

예시 (POST 요청):

```
POST /users HTTP/1.1
Host: localhost
Content-Type: application/json
Content-Length: 39
Expect: 100-continue

{"name": "Kim", "email": "kim@test.com"}
```

### 4.2 응답(Response) 메시지 구조

```
<HTTP-Version> <Status-Code> <Reason-Phrase>\r\n   ← Status Line
<Header-Name>: <Header-Value>\r\n                  ← Header
...
\r\n
<Body>
```

예시:

```
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 60
Connection: keep-alive

{"id": 1, "name": "Jaewon", "email": "jaewon@example.com"}
```

`Content-Length`와 `Connection` 헤더는 서버가 모든 응답에 공통으로 붙여준다. 지속 연결(Keep-Alive)에서는 연결이 끊기지 않으므로 "연결 종료 = 응답 끝"이라는 신호를 쓸 수 없다 — `Content-Length`가 없다면 클라이언트는 이 응답이 어디서 끝나는지 알 방법이 없어 다음 요청을 준비할 수 없다. 그래서 클라이언트는 `Content-Length`만큼 바이트를 읽어야 응답의 끝을 알 수 있다(6.4절, 7.2절 참고).

### 4.3 본 프로젝트에서 구현한 메서드

| Method | 의미 | 본 프로젝트에서의 처리 |
|---|---|---|
| GET | 리소스 조회 | `/users` 전체 조회 또는 `/users/{id}` 단건 조회 |
| HEAD | GET과 동일하되 응답 바디 없이 헤더만 반환 | GET과 같은 로직으로 존재 여부만 판단, 바디 미전송 |
| POST | 새 리소스 생성 | `/users`에 JSON 바디(`name`, `email`)로 새 사용자 추가 |
| PUT | 기존 리소스 수정(대체/갱신) | `/users/{id}`의 name/email을 갱신 |
| DELETE | 리소스 삭제 | `/users/{id}` 삭제 (과제 요구 4종 메서드 외 추가 구현) |

### 4.4 상태 코드 분류

| 분류 | 의미 | 본 프로젝트 사용 예 |
|---|---|---|
| 1xx (Informational) | 요청을 받았고 처리를 계속함 | `100 Continue` — POST/PUT에서 `Expect: 100-continue` 처리 시 |
| 2xx (Success) | 요청 성공 | `200 OK`, `201 Created`, `204 No Content` |
| 4xx (Client Error) | 클라이언트 요청 오류 | `400 Bad Request`, `404 Not Found` |
| 5xx (Server Error) | 서버 처리 오류 | 본 프로젝트에서는 미사용 (미구현 케이스) |

### 4.5 `Expect: 100-continue` 흐름 (1xx 상태 코드 구현)

바디가 있는 요청(POST, PUT)에서 클라이언트는 바디를 곧바로 보내지 않고, 먼저 `Expect: 100-continue` 헤더를 포함한 헤더만 전송한다. 서버는 이를 확인하고 `HTTP/1.1 100 Continue`를 먼저 응답하며, 클라이언트는 이 100 응답을 수신한 이후에 실제 바디를 전송한다.

```
Client                                Server
  |--- Header (Expect:100-continue) -->|
  |<--------- 100 Continue ------------|
  |--- Body -------------------------->|
  |<--------- 최종 응답(200/201/400 등) -|
```

이 구조 덕분에 POST/PUT 요청 시마다 실제로 1xx 상태 코드가 한 번씩 발생한다. 다만 클라이언트 콘솔에는 각 요청의 최종 상태 코드만 출력하도록 되어 있어(7.2절 참고) 이 `100 Continue` 자체는 화면에 별도로 찍히지 않으며, 실제로 주고받았는지는 10장의 Wireshark 캡처에서 확인할 수 있다.

---

## 5. 프로그램 구조 및 파일 설명

```
Socket_HTTP_Project/
├── server.py         # TCP 서버 + HTTP 요청 파싱/응답 (핵심 로직)
├── client.py         # TCP 클라이언트 + HTTP 요청 생성 + 테스트 케이스 실행기
├── seed_users.py      # SQLite DB 초기화 및 샘플 데이터 20건 삽입
└── database/
    └── users.db        # SQLite DB 파일 (users 테이블)
```

### 5.1 `seed_users.py`

`users` 테이블(`id`, `name`, `email`)을 생성하고, `Jaewon` ~ `Rina`까지 20명의 샘플 사용자를 삽입한다. `id`는 `INTEGER PRIMARY KEY AUTOINCREMENT`로 선언되어 있어 자동 증가한다. 서버를 처음 실행하기 전, 혹은 DB를 초기 상태로 되돌리고 싶을 때(특히 시연 영상 촬영 직전) `database/users.db` 파일을 삭제한 뒤 본 스크립트를 재실행하면 `id`가 1부터 다시 시작하는 깨끗한 상태로 초기화된다.

### 5.2 `server.py`

포트 8080에서 TCP 연결을 대기하다가, 연결이 들어오면 클라이언트가 연결을 끊을 때까지 같은 소켓으로 요청 데이터 수신 → 파싱 → 메서드별 분기 처리 → SQLite 조회/변경 → HTTP 응답 문자열 조립 → 전송을 반복하는 반복 서버(Keep-Alive).

### 5.3 `client.py`

프로그램 시작 시 TCP 연결을 한 번만 맺고, 사용자가 번호를 입력할 때마다 `send_request()`로 같은 소켓에 요청을 보내고 응답의 상태 코드를 콘솔에 출력한다. `test_cases` 딕셔너리에 과제에서 요구하는 "Method-상태코드" 조합 9가지가 정의되어 있으며, 사용자가 `q`를 입력하면 그때 소켓을 닫고 프로그램을 종료한다.

---

## 6. 서버(server.py) 동작 과정

### 6.1 초기화

```python
serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.bind(('', serverPort))
serverSocket.listen()
print('The server is ready to receive')
```

TCP 소켓을 생성하고 8080 포트에 바인딩한 뒤, `listen()`으로 연결 대기 상태에 진입한다. `bind(('', serverPort))`에서 IP를 공백으로 지정하면 서버 PC의 모든 네트워크 인터페이스에서 오는 연결을 받아들이므로, `localhost` 실습뿐 아니라 2대 PC 환경에서도 별도 수정 없이 동작한다.

### 6.2 연결 수락과 Keep-Alive 루프

```python
connectionSocket, addr = serverSocket.accept()

while True: # 클라이언트가 닫을 때까지 같은 TCP 연결로 여러 요청을 순서대로 처리
    request = connectionSocket.recv(1024).decode()

    if not request: # 클라이언트가 연결을 끊음 (예: 사용자가 q 입력 후 close())
        break

    while "\r\n\r\n" not in request: # 헤더가 한 번에 다 안 왔으면 마저 수신
        more = connectionSocket.recv(1024).decode()
        if not more:
            break
        request += more

    request_line = request.split("\r\n")[0]
    method, path, version = request_line.split()
```

`accept()`로 클라이언트별 전용 소켓을 얻은 뒤, 요청 하나를 처리하고 곧바로 닫는 대신 내부 `while True:` 루프를 돈다. 매 반복마다 `recv()`로 새 요청을 기다리며, 클라이언트가 소켓을 닫으면(사용자가 `q`를 입력해 `close()`가 호출되면) `recv()`가 빈 문자열을 반환하므로 이를 루프 종료 조건으로 삼는다. 첫 줄(Request Line)은 공백 기준으로 분리하여 Method/Path/HTTP-Version을 추출한다.

이어서 헤더 영역(`\r\n\r\n` 이전)만 잘라내어 한 줄씩 검사하며 `Content-Length`와 `Expect: 100-continue` 유무를 확인한다.

```python
header_part = request.split("\r\n\r\n")[0]
for line in header_part.split("\r\n")[1:]:
    if line.lower().startswith("content-length:"):
        content_length = int(line.split(":")[1].strip())
    if line.lower().startswith("expect:") and "100-continue" in line.lower():
        expect_continue = True
```

`Expect: 100-continue`가 확인되면 바디를 받기 전에 먼저 `100 Continue`를 응답하고, 이후 `Content-Length`만큼 바디를 마저 수신한다(첫 `recv`에 바디 일부가 이미 포함된 경우까지 고려하여 누락 없이 수신).

### 6.3 메서드별 분기 처리

| 분기 | 처리 내용 | 반환 상태 코드 |
|---|---|---|
| `GET /users` | 전체 사용자 목록을 JSON 배열로 반환 | 200 |
| `GET /users/{id}` | 단건 조회, 없으면 오류 | 200 / 404 |
| `GET` (그 외 경로) | 정의되지 않은 경로 | 404 |
| `HEAD /users`, `HEAD /users/{id}` | GET과 동일 로직으로 존재 여부만 판단, 바디는 응답하지 않음 | 200 / 404 |
| `POST /users` | 바디의 `name`, `email` 검증 후 DB에 삽입 | 201 / 400(필드 누락) |
| `PUT /users/{id}` | 대상 존재 확인 후 `name`/`email` 갱신 | 200 / 404 |
| `DELETE /users/{id}` | 대상 존재 확인 후 삭제 | 204 / 404 |
| 그 외 메서드 | 정의되지 않은 메서드 | 405 |

각 분기는 `sqlite3.connect("database/users.db")`로 DB에 접속하여 조회(`SELECT`)/삽입(`INSERT`)/수정(`UPDATE`)/삭제(`DELETE`) SQL을 실행하고, 결과에 따라 `json.dumps()`로 JSON 바디를 만들어 HTTP 응답 문자열에 붙인다.

### 6.4 응답 조립·전송과 연결 유지

```python
head, _, resp_body = response.partition("\r\n\r\n")
body_bytes = resp_body.encode()
response_bytes = (
    head.encode()
    + f"\r\nContent-Length: {len(body_bytes)}\r\nConnection: keep-alive\r\n\r\n".encode()
    + body_bytes
)

connectionSocket.send(response_bytes) # 응답 전송, 연결은 닫지 않고 다음 요청을 기다림
```

각 분기에서 만든 `response` 문자열(상태 라인 + 기존 헤더 + 빈 줄 + 바디)을 `\r\n\r\n` 기준으로 헤더부/바디부로 나눈 뒤, 실제 바디 바이트 길이로 계산한 `Content-Length`와 `Connection: keep-alive`를 끝에 추가해서 다시 조립한다. 응답을 보낸 뒤에는 연결을 닫지 않고 내부 `while True` 루프 맨 위로 돌아가 같은 소켓으로 다음 요청을 기다린다. 클라이언트가 연결을 끊었을 때(6.2절의 `if not request: break`)만 루프를 빠져나와 바깥쪽 `while True`로 돌아가 `connectionSocket.close()`를 호출하고 다음 클라이언트의 `accept()`를 대기한다.

---

## 7. 클라이언트(client.py) 동작 과정

### 7.1 TCP 연결은 프로그램 시작 시 단 한 번

```python
clientSocket = socket(AF_INET, SOCK_STREAM) # TCP 연결은 여기서 딱 한 번만 생성
clientSocket.connect((serverName, serverPort))
print("TCP Connect")
```

기존에는 `send_request()`가 호출될 때마다 새 TCP 연결을 맺었지만(HTTP/1.0 스타일), 이제는 프로그램 최상단에서 `connect()`를 한 번만 호출하고 이 소켓(`clientSocket`)을 이후 루프 전체에서 재사용한다.

### 7.2 요청 생성과 100 Continue 처리 — `send_request()`

```python
def send_request(clientSocket, method, path, body=""):
    header_lines = f"Host: {serverName}"
    if body:
        header_lines += f"\r\nContent-Type: application/json\r\nContent-Length: {len(body.encode())}"
        header_lines += "\r\nExpect: 100-continue"
    header_lines += "\r\nConnection: keep-alive" # 이 연결을 계속 쓸 것임을 알림

    request = f"{method} {path} HTTP/1.1\r\n{header_lines}\r\n\r\n"
    clientSocket.send(request.encode()) # 같은 소켓으로 요청 전송 (새 연결 생성 없음)

    if body:
        interim = clientSocket.recv(1024).decode()
        if interim.startswith("HTTP/1.1 100"):
            clientSocket.send(body.encode()) # 100 Continue를 받은 후에 바디 전송
```

이미 연결된 `clientSocket`을 인자로 받아 그 소켓으로 요청을 보낸다. `Method`, `Path`, `Host` 헤더를 조합해 Request Line + Header를 만들고, 바디가 있는 경우(POST/PUT)에는 `Content-Type`, `Content-Length`, `Expect: 100-continue` 헤더를 추가한 뒤 `Connection: keep-alive`를 덧붙인다. 서버로부터 `100 Continue`를 받은 뒤에야 실제 JSON 바디를 전송하는 흐름은 이전과 동일하다.

### 7.3 응답 수신 — `recv_response()`

```python
def recv_response(clientSocket):
    buffer = b""
    while b"\r\n\r\n" not in buffer: # 헤더가 다 도착할 때까지 수신
        chunk = clientSocket.recv(4096)
        if not chunk:
            break
        buffer += chunk

    header_bytes, _, body_bytes = buffer.partition(b"\r\n\r\n")
    header_text = header_bytes.decode()

    content_length = 0
    for line in header_text.split("\r\n")[1:]:
        if line.lower().startswith("content-length:"):
            content_length = int(line.split(":")[1].strip())

    while len(body_bytes) < content_length: # Content-Length만큼 바디가 다 도착할 때까지 수신
        chunk = clientSocket.recv(4096)
        if not chunk:
            break
        body_bytes += chunk

    return header_text + "\r\n\r\n" + body_bytes.decode()
```

기존에는 `clientSocket.recv(4096)` 한 번으로 응답을 통째로 읽었는데, 이는 서버가 응답 직후 곧바로 연결을 닫아주었기 때문에 우연히 문제없이 동작했던 것이다. Keep-Alive로 연결이 계속 열려 있으면 "연결이 닫히면 응답 끝"이라는 신호를 쓸 수 없으므로, 응답 헤더의 `Content-Length`를 읽어 그 바이트 수만큼 바디가 다 올 때까지 `recv()`를 반복하도록 고쳤다. `send_request()`는 이 함수로 받은 응답에서 상태 코드만 뽑아 출력한다.

```python
response = recv_response(clientSocket)
status_line = response.split("\r\n")[0] # "HTTP/1.1 200 OK"
status_only = status_line.split(" ", 1)[1] # "200 OK"

print(f"{method} {path}")
print(status_only)
```

### 7.4 대화형 실행 루프

```python
test_cases = {
    "1": ("GET", "/users", ""),
    "2": ("GET", "/notfound", ""),
    "3": ("HEAD", "/users", ""),
    "4": ("POST", "/users", '{"name": "Kim", "email": "kim@test.com"}'),
    ...
}

while True:
    choice = input("번호 입력: ").strip()

    if choice.lower() == "q": # 종료할 때만 연결을 닫음
        break

    if choice not in test_cases:
        print("잘못된 입력입니다.")
        continue

    method, path, body = test_cases[choice]
    send_request(clientSocket, method, path, body) # 같은 소켓으로 요청 전송

clientSocket.close()
print("TCP Close")
```

사용자가 번호(1~9)를 입력할 때마다 이미 연결된 `clientSocket`으로 요청을 보내고, `q`를 입력하면 그때 루프를 빠져나와 소켓을 닫는다. 즉 **TCP 연결 생성은 프로그램 시작 시 1번, 종료는 `q` 입력 시 1번뿐**이고, 그 사이의 모든 요청/응답은 같은 소켓 위에서 오간다. 과제에서 요구한 "Method-상태코드 5개 이상" 조건을 충족하기 위해 GET/HEAD/POST/PUT/DELETE 5개 메서드 각각에 대해 성공/실패 케이스를 나누어 총 9개 조합을 준비하였다.

> **주의**: `DELETE-204`에 해당하는 `8`번 케이스는 `/users/20`을 고정적으로 삭제하도록 구현되어 있으므로, 이미 한 번 삭제된 이후 재실행하면 `404 Not Found`가 반환된다. 204 응답을 재현하려면 시연 전에 `seed_users.py`를 다시 실행하여 DB를 초기 상태로 되돌려야 한다.

---

## 8. 실행 방법

### 8.1 사전 준비 (DB 초기화)

```bash
cd Socket_HTTP_Project
python seed_users.py
```

실행 결과 예시:
```
20명의 유저 추가 완료
```

### 8.2 서버 실행 (터미널 1)

```bash
python server.py
```

실행 결과:
```
The server is ready to receive
```

서버는 이 상태로 계속 대기하며, 클라이언트 요청이 올 때까지 종료되지 않는다.

### 8.3 클라이언트 실행 (터미널 2, 별도 콘솔)

```bash
python client.py
```

실행하면 아래와 같이 출력되고, TCP 연결을 맺은 뒤 번호 입력을 기다린다.

```
프로그램 시작

사용 가능한 번호:
  1. GET /users
  2. GET /notfound
  3. HEAD /users
  4. POST /users
  5. POST /users
  6. PUT /users/1
  7. PUT /users/9999
  8. DELETE /users/20
  9. DELETE /users/9999
  q. 종료

TCP Connect

번호 입력:
```

번호(1~9)를 입력할 때마다 이미 맺어둔 같은 TCP 연결로 해당 HTTP 요청이 전송되고, 응답 상태 코드가 출력된 뒤 다시 `번호 입력:` 프롬프트로 돌아온다. `q`를 입력해야 비로소 연결이 닫히고 프로그램이 종료된다(9장 참고).

### 8.4 2대 PC 환경으로 실행할 경우

1. 서버 PC에서 `python server.py` 실행, 방화벽에서 TCP 8080 인바운드 허용
2. 클라이언트 PC의 `client.py`에서 `serverName = 'localhost'`를 서버 PC의 실제 IP(예: `192.168.0.10`)로 변경
3. 두 PC가 같은 네트워크(같은 공유기/스위치)에 연결되어 있어야 함

---

## 9. HTTP 요청/응답 실행 결과 (Method-상태코드 케이스)

아래는 `seed_users.py`로 DB를 초기화한 직후, `python server.py` → `python client.py`를 실행하여 번호 `1`부터 `9`까지 순서대로 입력하고 마지막에 `q`로 종료한 **실제 실행 로그**이다. TCP 연결은 `TCP Connect` 시점에 한 번만 맺어졌고, 9개 요청 모두 그 연결 하나로 오간 뒤 `q` 입력 시점에 `TCP Close`로 닫혔다.

```
프로그램 시작

사용 가능한 번호:
  1. GET /users
  2. GET /notfound
  3. HEAD /users
  4. POST /users
  5. POST /users
  6. PUT /users/1
  7. PUT /users/9999
  8. DELETE /users/20
  9. DELETE /users/9999
  q. 종료

TCP Connect

번호 입력: 1
GET /users
200 OK

번호 입력: 2
GET /notfound
404 Not Found

번호 입력: 3
HEAD /users
200 OK

번호 입력: 4
POST /users
201 Created

번호 입력: 5
POST /users
400 Bad Request

번호 입력: 6
PUT /users/1
200 OK

번호 입력: 7
PUT /users/9999
404 Not Found

번호 입력: 8
DELETE /users/20
204 No Content

번호 입력: 9
DELETE /users/9999
404 Not Found

번호 입력: q
TCP Close
프로그램 종료
```

클라이언트 콘솔에는 요청(`Method Path`)과 최종 상태 코드만 출력되도록 되어 있다(7.3절). 각 케이스의 상세 동작은 다음과 같다.

| # | 요청 | 응답 | 설명 |
|---|---|---|---|
| 1 | `GET /users` | `200 OK` | DB에 저장된 20명의 사용자 정보를 JSON 배열로 반환 |
| 2 | `GET /notfound` | `404 Not Found` | 정의되지 않은 경로 → `{"error": "not found"}` |
| 3 | `HEAD /users` | `200 OK` | GET과 같은 로직으로 존재 여부만 판단, 바디 없이 헤더만 응답 |
| 4 | `POST /users` (정상 바디) | `100 Continue` → `201 Created` | `Expect: 100-continue`로 100 응답을 먼저 받은 뒤 바디 전송 → DB에 삽입되어 자동 증가된 `id: 21`로 생성됨 |
| 5 | `POST /users` (빈 바디 `{}`) | `100 Continue` → `400 Bad Request` | `name`/`email` 필드 누락 감지 → `{"error": "name and email are required"}` |
| 6 | `PUT /users/1` | `100 Continue` → `200 OK` | 대상이 존재하므로 `name`/`email`을 요청 바디 값으로 전체 교체 후 갱신된 정보 반환 |
| 7 | `PUT /users/9999` | `100 Continue` → `404 Not Found` | 존재하지 않는 `id` → `{"error": "user not found"}` |
| 8 | `DELETE /users/20` | `204 No Content` | 삭제 성공, 반환할 바디가 없으므로 `204` (바디 없이 상태 라인만) |
| 9 | `DELETE /users/9999` | `404 Not Found` | 이미 없는 `id` → `{"error": "user not found"}` |

4, 5, 6, 7번 케이스는 요청에 바디가 있어 `Expect: 100-continue` → `100 Continue` 흐름이 먼저 발생하지만(4.5절), 콘솔에는 최종 상태 코드만 찍히므로 `100 Continue` 자체는 로그에 보이지 않는다. 이 1xx 응답이 실제로 오갔는지는 10장의 Wireshark 캡처에서 확인한다.

과제 예시에서 제시한 "GET-4xx, GET-2xx, HEAD-1xx, POST-2xx, POST-1xx" 5가지 조합을 모두 포함하며(HEAD 자체는 1xx를 발생시키지 않으므로, 1xx는 바디를 포함하는 POST/PUT 요청에서 재현), 총 9개의 서로 다른 Method-상태코드 조합으로 요구 조건(5개 이상)을 초과 달성하였다.

---

## 10. Wireshark 패킷 캡처 및 분석

본 장에서는 9장에서 다룬 9개 케이스 중, 영상 시연용으로 선정한 아래 **5개 핵심 케이스**를 중심으로 Wireshark 캡처 결과를 정리한다. 이 5개는 과제가 필수로 요구하는 4개 메서드(GET/HEAD/POST/PUT)를 모두 포함하고, 1xx/2xx/4xx 상태 코드 분류도 겹치지 않게 구성한 조합이다.

| # | 케이스 | 메서드 | 상태 코드 |
|---|---|---|---|
| 1 | GET /users | GET | 200 OK |
| 2 | GET /notfound | GET | 404 Not Found |
| 3 | HEAD /users | HEAD | 200 OK |
| 4 | POST /users (정상 바디) | POST | 100 Continue → 201 Created |
| 5 | PUT /users/9999 | PUT | 100 Continue → 404 Not Found |
| 6 | DELETE /users/20 | DELETE | 204 No Content |

### 10.1 캡처 방법

1. Wireshark 실행 → 캡처 인터페이스로 **Loopback(localhost 통신용, `Npcap Loopback Adapter` 또는 `Adapter for loopback traffic capture`)** 선택
2. 캡처 필터 또는 디스플레이 필터에 `tcp.port == 8080` 입력하여 8080 포트 트래픽만 확인
3. `python server.py` 실행 → `python client.py` 실행 순서로 캡처 시작 후, 번호를 `1, 2, 3, 4, 7`(위 5개 케이스) 순서로 입력하고 `q`로 종료
4. Keep-Alive로 TCP 연결이 하나만 열리므로, 위 5개 요청·응답이 모두 **같은 `tcp.stream` 번호** 안에 순서대로 들어있다. `Follow → TCP Stream`으로 열어 스크롤하며 요청 순서대로 확인
5. HTTP로 필터링하려면 `http` 디스플레이 필터도 함께 사용 가능 (단, Wireshark가 8080 포트를 HTTP로 자동 인식하지 못하면 패킷에서 우클릭 → `Decode As` → HTTP로 지정)

### 10.2 확인 항목

- **3-way Handshake**: `SYN` → `SYN, ACK` → `ACK` 3개 패킷이 `TCP Connect` 시점에 **한 번만** 발생
- **HTTP Request 패킷**: `GET /users HTTP/1.1`, `POST /users HTTP/1.1` 등 Request Line과 `Content-Length`, `Expect: 100-continue`, `Connection: keep-alive`
- **100 Continue 패킷**: POST/PUT 요청 시 서버가 바디를 받기 전에 별도의 작은 응답 패킷(`HTTP/1.1 100 Continue`)을 먼저 보냄
- **HTTP Response 패킷**: 상태 코드별 응답(`200 OK`, `404 Not Found`, `201 Created` 등)이 페이로드에 텍스트로 담기며, `Content-Length`/`Connection: keep-alive` 헤더도 함께 확인 가능
- **연결이 유지됨(FIN 없음)**: 5개 요청·응답 사이사이에는 `FIN`이 나타나지 않고, 같은 연결 위에서 바로 다음 요청이 이어진다. `q` 입력으로 클라이언트가 `close()`를 호출하는 시점에만 `FIN, ACK` 4-way termination이 한 번 발생한다 — 이 부분이 이전(요청마다 연결을 닫던) 버전과 가장 크게 달라진 지점이다.

### 10.3 케이스별 캡처 화면

> **참고**: 아래 6개 스크린샷은 Keep-Alive를 도입하기 전, 요청마다 새 TCP 연결을 맺고 응답 직후 바로 닫던 버전으로 캡처한 것이다. 그래서 각 캡처마다 3-way handshake와 `FIN, ACK` 종료가 개별적으로 등장한다. 지금 코드로 다시 캡처하면 10.1~10.2에서 설명한 대로 5개 요청이 handshake 한 번, 종료 한 번을 공유하는 **하나의 `tcp.stream`** 안에 이어져 보인다 — Request Line, 100 Continue, 상태 코드 등 개별 패킷의 내용 자체는 동일하게 확인할 수 있다.

**① GET /users → 200 OK**

![GET /users 요청 전체 캡처](images/get-200-stream.png)

`tcp.port == 8080` 필터로 캡처한 화면이다. 패킷 49-51번에서 `SYN → SYN,ACK → ACK` 3-way handshake가 이루어지고, 52번 패킷에서 `GET /users HTTP/1.1` 요청이 전송된다. 53번은 서버의 TCP ACK이고, 54번 패킷(`[PSH, ACK]`, Len=1250)에 `HTTP/1.1 200 OK` 상태 라인과 JSON 바디가 함께 담겨 전송된 것을 `Info` 컬럼에서 확인할 수 있다. 마지막 58-59번 패킷에서 `FIN, ACK`로 연결이 종료된다.

**② GET /notfound → 404 Not Found**

![GET /notfound Follow TCP Stream](images/get-404-stream.png)
- 확인 포인트: 요청 패킷의 `GET /notfound HTTP/1.1`, 응답 패킷의 `HTTP/1.1 404 Not Found`와 `{"error": "not found"}` 바디가 페이로드에 그대로 보이는지 (`Follow TCP Stream` 권장)

**③ HEAD /users → 200 OK**

![HEAD /users Follow TCP Stream](images/head-200-stream.png)
- 확인 포인트: 요청은 `HEAD /users HTTP/1.1`이지만 응답 패킷에 `Content-Type` 헤더 뒤에 **바디가 없다**는 점을 GET-200 캡처와 비교해서 보여주면 좋음

**④ POST /users → 100 Continue → 201 Created**

![POST /users Follow TCP Stream](images/post-201-stream.png)

패킷 상세 패널(Packet Details)에서 `Hypertext Transfer Protocol` 트리를 펼친 화면이다. `Response Version: HTTP/1.1`, `Status Code: 100`, `Response Phrase: Continue`가 각각의 필드로 파싱되어 있다. 이는 `Expect: 100-continue` 헤더를 받은 서버가 클라이언트의 바디 전송을 승인하며 보내는 응답이다(4.5절 참고). 이 패킷 자체가 과제에서 요구하는 **1xx 상태 코드** 캡처에 해당한다.
같은 연결(`tcp.stream`)에서 이어지는 헤더 요청 패킷(`Content-Length`, `Expect: 100-continue` 포함) + 바디 패킷 + 최종 `201 Created` 응답까지 `Follow TCP Stream`으로 본 전체 화면

**⑤ PUT /users/9999 → 100 Continue → 404 Not Found**

![PUT /users/9999 Follow TCP Stream](images/put-404-stream.png)
- 확인 포인트: POST와 동일하게 `Expect: 100-continue` → `100 Continue` 흐름이 한 번 더 재현되며, 최종 응답이 `404 Not Found`이다.

**⑥ DELETE /users/20 → 204 No Content**

![DELETE /users/20 Follow TCP Stream](images/delete-204-stream.png)
- 확인 포인트: `DELETE /users/20 HTTP/1.1` 요청은 바디가 없어 `100 Continue` 과정 없이 바로 응답이 오며, 삭제 성공 응답은 `HTTP/1.1 204 No Content`로 **바디 없이 상태 라인만** 온다는 점이 다른 성공 응답과 다르다.

---

## 11. 결론 및 소감

본 프로젝트를 통해 HTTP가 TCP 위에서 단순한 텍스트 규약으로 동작한다는 사실을 코드 레벨에서 직접 체감할 수 있었다. 평소 `requests.get()` 한 줄로 처리되던 GET 요청이 실제로는 `GET /path HTTP/1.1\r\nHost: ...\r\n\r\n`이라는 정해진 형식의 문자열이며, 서버는 이를 파싱해 상태 코드와 함께 응답을 조립해 돌려준다는 것을 직접 구현하며 이해했다.

또한 GET/HEAD/POST/PUT/DELETE 5개 메서드에 대해 성공/실패 케이스를 나누어 총 9개의 Method-상태코드 조합(1xx, 2xx, 4xx 포함)을 재현함으로써, 상태 코드가 단순한 숫자가 아니라 클라이언트-서버 간 약속된 의미 체계임을 확인할 수 있었다. Wireshark로 실제 패킷을 캡처하면 이 텍스트 기반 프로토콜이 TCP 세그먼트에 그대로 실려 전송된다는 것, 그리고 3-way handshake와 100 Continue 같은 세부 흐름이 실제로 존재한다는 것을 눈으로 확인할 수 있었다.

개발 과정에서 처음에는 요청마다 새 TCP 연결을 맺고 응답 직후 곧바로 닫는 구조로 구현했는데, 이는 요청을 여러 번 보낼 방법(Keep-Alive)이 없다는 점에서 HTTP/1.1의 이름값에 맞지 않았다. 이를 하나의 TCP 연결로 여러 요청을 처리하는 지속 연결(Persistent Connection) 구조로 바꾸면서, "연결을 닫는 것"이 아니라 "`Content-Length`로 응답의 끝을 알리는 것"이 메시지 프레이밍의 본질이라는 점을 체감했다. 연결을 유지한 채로는 소켓이 닫히는 순간을 응답의 끝으로 쓸 수 없으므로, 클라이언트가 다음 요청을 준비하려면 서버가 반드시 바디 길이를 명시해야 했다.

---

## 부록 A. 전체 소스코드

전체 소스코드는 다음 파일에 포함되어 있으며, 본 문서에는 핵심 로직만 발췌하여 설명하였다.

- `server.py` — TCP 서버 및 HTTP 요청 처리 로직, Keep-Alive 루프 포함 (약 180줄)
- `client.py` — TCP 클라이언트 및 대화형 실행 루프 (약 100줄)
- `seed_users.py` — DB 초기화 스크립트 (약 30줄)

(각 파일의 상세 주석은 소스코드 내 인라인 주석을 참고)

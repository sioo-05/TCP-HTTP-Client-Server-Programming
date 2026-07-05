from socket import *
import json

serverName = 'localhost'
serverPort = 8080


def recv_response(clientSocket):
    # 헤더가 다 도착할 때까지 수신
    buffer = b""
    while b"\r\n\r\n" not in buffer:
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

    # Content-Length만큼 바디가 다 도착할 때까지 수신 (Keep-Alive라 연결 종료로는 끝을 알 수 없음)
    while len(body_bytes) < content_length:
        chunk = clientSocket.recv(4096)
        if not chunk:
            break
        body_bytes += chunk

    return header_text + "\r\n\r\n" + body_bytes.decode()


def send_request(clientSocket, method, path, body=""):
    header_lines = f"Host: {serverName}"
    if body:
        header_lines += f"\r\nContent-Type: application/json\r\nContent-Length: {len(body.encode())}" # 헤더 라인 추가
        header_lines += "\r\nExpect: 100-continue" # 바디가 있으면 100 Continue부터 확인
    header_lines += "\r\nConnection: keep-alive" # 이 연결을 계속 쓸 것임을 알림

    request = f"{method} {path} HTTP/1.1\r\n{header_lines}\r\n\r\n" # 요청 메시지
    clientSocket.send(request.encode()) # 같은 소켓으로 요청 전송 (새 연결 생성 없음)

    if body:
        interim = clientSocket.recv(1024).decode()
        if interim.startswith("HTTP/1.1 100"):
            clientSocket.send(body.encode()) # 100 Continue를 받은 후에 바디 전송

    response = recv_response(clientSocket) # 서버로부터 응답 받기 (Content-Length 기준으로 정확히 다 읽음)
    status_line = response.split("\r\n")[0] # 예: "HTTP/1.1 200 OK"
    status_only = status_line.split(" ", 1)[1] # 예: "200 OK"

    body_only = response.split("\r\n\r\n", 1)[1]

    print(f"{method} {path}")
    print(status_only)
    if body_only:
        print(body_only)
    print()


# Method-상태코드 케이스 (5개 이상, CRUD 전체)
test_cases = {
    "1": ("GET", "/users", ""),
    "2": ("GET", "/notfound", ""),
    "3": ("HEAD", "/users", ""),
    "4": ("POST", "/users", '{"name": "Kim", "email": "kim@test.com"}'),
    "5": ("POST", "/users", "{}"),
    "6": ("PUT", "/users/1", '{"name": "Kim Updated", "email": "kim.updated@test.com"}'),
    "7": ("PUT", "/users/9999", '{"name": "Ghost", "email": "ghost@test.com"}'),
    "8": ("DELETE", "/users/20", ""),
    "9": ("DELETE", "/users/9999", ""),
}

print("프로그램 시작")
print()
print("사용 가능한 번호:")
for key, (method, path, _) in test_cases.items():
    print(f"  {key}. {method} {path}")
print("  q. 종료")
print()

clientSocket = socket(AF_INET, SOCK_STREAM) # TCP 연결은 여기서 딱 한 번만 생성
clientSocket.connect((serverName, serverPort))
print("TCP Connect")
print()

while True:
    choice = input("번호 입력: ").strip()

    if choice.lower() == "q": # 종료할 때만 연결을 닫음
        break

    if choice not in test_cases:
        print("잘못된 입력입니다.")
        print()
        continue

    method, path, body = test_cases[choice]
    send_request(clientSocket, method, path, body) # 같은 소켓으로 요청 전송

clientSocket.close()
print("TCP Close")
print("프로그램 종료")

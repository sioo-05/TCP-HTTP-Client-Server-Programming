from socket import *
import json

serverName = 'localhost'
serverPort = 8080 


def send_request(method, path, body=""):
    clientSocket = socket(AF_INET, SOCK_STREAM) # 요청마다 새 연결
    clientSocket.connect((serverName, serverPort)) # 연결 

    header_lines = f"Host: {serverName}" 
    if body:
        header_lines += f"\r\nContent-Type: application/json\r\nContent-Length: {len(body.encode())}" # 헤더 라인 추가
        header_lines += "\r\nExpect: 100-continue" # 바디가 있으면 100 Continue부터 확인

    request = f"{method} {path} HTTP/1.1\r\n{header_lines}\r\n\r\n" # 요청 메시지
    clientSocket.send(request.encode()) # 요청 메시지 전송

    if body:
        interim = clientSocket.recv(1024).decode() 
        print(f"[{method} {path}] interim ->", interim.split("\r\n")[0])
        if interim.startswith("HTTP/1.1 100"):
            clientSocket.send(body.encode()) # 100 Continue를 받은 후에 바디 전송

    response = clientSocket.recv(4096).decode() # 서버로부터 응답 받기
    status_line = response.split("\r\n")[0] 
    print(f"[{method} {path}] -> {status_line}")
    print(response)
    print("-" * 60)

    clientSocket.close()
    return response


def test_delete_success():
    # 삭제할 대상을 미리 하나 생성한 뒤, 그 id를 삭제해서 204를 재현 가능하게 함
    created = send_request("POST", "/users", '{"name": "Temp", "email": "temp@test.com"}')
    body_json = created.split("\r\n\r\n", 1)[1]
    new_id = json.loads(body_json)["id"]
    send_request("DELETE", f"/users/{new_id}")


# 과제에서 요구하는 Method-상태코드 케이스 (5개 이상, CRUD 전체)
test_cases = {
    "1": ("GET-200", lambda: send_request("GET", "/users")),
    "2": ("GET-404", lambda: send_request("GET", "/notfound")),
    "3": ("HEAD-200", lambda: send_request("HEAD", "/users")),
    "4": ("POST-201", lambda: send_request("POST", "/users", '{"name": "Kim", "email": "kim@test.com"}')),
    "5": ("POST-400", lambda: send_request("POST", "/users", "{}")),
    "6": ("PUT-200", lambda: send_request("PUT", "/users/1", '{"name": "Kim Updated"}')),
    "7": ("PUT-404", lambda: send_request("PUT", "/users/9999", '{"name": "Ghost"}')),
    "8": ("DELETE-204",lambda:send_request("DELETE", "/users/1")),
    "9": ("DELETE-404", lambda: send_request("DELETE", "/users/9999")),
}

print("테스트할 케이스를 선택하세요:")
for key, (label, _) in test_cases.items():
    print(f"  {key}. {label}")
print("  0. 전체 실행")

choice = input("번호 입력: ").strip()

if choice == "0":
    for key, (label, func) in test_cases.items():
        print(f"=== {label} ===")
        func()
elif choice in test_cases:
    label, func = test_cases[choice]
    print(f"=== {label} ===")
    func()
else:
    print("잘못된 입력입니다.")

from socket import *
serverPort = 8080 # 서버 포트 
serverSocket = socket(AF_INET, SOCK_STREAM) # 서버 소켓 생성
serverSocket.bind(('',serverPort)) # IP와 Port 지정 (모든 네트워크 인터페이스(IP)에서 8080 포트로 들어오는 연결을 받겠다.)
serverSocket.listen() # 서버 연결 대기
print('The server is ready to receive')
while True:
    connectionSocket, addr = serverSocket.accept() # 클라이언트의 연결 요청 수락 / 서버는 계속 새로운 클라이언트를 받아야 하기 때문에 항상 새 소켓을 만듦
    sentence = connectionSocket.recv(1024).decode()
    capitalSentence = sentence.upper()
    connectionSocket.send(capitalSentence.encode())
    
    connectionSocket.close()
    
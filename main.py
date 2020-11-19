import socket
import os
import time
from concurrent.futures import ThreadPoolExecutor
import threading

HOST = ''
PORT = 80
#index目录
ROOT = "/var/www"
#线程池容量
MAX_WORKER = 4
#最大容许错误请求数
MAX_ERROR_COUNT = 5
#黑名单
black_mutex = threading.Lock()
black_list = set()
#错误请求计数
error_mutex = threading.Lock()
error_count = dict()
#从请求中读取文件路径
def read_request(request):
    get = False
    first = request.find(' ')
    second = request.find(' ', first + 1)
    return request[:first], request[first + 1:second]
#检查是否有返回上层操作
def safe_check(file_path):
    if file_path.find('/..') >= 0:
        return False
    else:
        return True
#处理请求函数
def handle_connection(client_connection, client_address, current_time):
    localtime = time.localtime(time.time())
    client_address = client_address[0]
    #查询是否在黑名单中
    if client_address in black_list:
        client_connection.close()
        print(current_time + ' ' + client_address + ' Refused')
        return

    request = client_connection.recv(1024).decode("utf-8")
    method, file_path = read_request(request)
    #默认请求
    if file_path == '/':
        file_path = '/index.html'
    print(current_time + ' ' + client_address + ' ' + method  + ' ' + file_path)
    code = 200
    #发送文件
    if safe_check(file_path):
        try:
            f = open(ROOT + file_path,'rb')
            http_response = f.read();
            try:
                client_connection.sendall(http_response)
            except:
                code = 200
            f.close()
        except:
            client_connection.sendall("HTTP/1.1 404 NOT FOUND".encode("utf-8"))
            success = False
            code = 404
    else:
        code = 403
        client_connection.sendall("HTTP/1.1 403 FORBIDDEN".encode("utf-8"))

    if code != 200:
        error_mutex.acquire()
        if client_address in error_count:
            error_count[client_address] += 1
            if error_count[client_address] >= MAX_ERROR_COUNT:
                black_mutex.acquire()
                black_list.add(client_address)
                black_mutex.release()
        else:
            error_count[client_address] = 1
        error_mutex.release()
    client_connection.close()

if __name__ == "__main__":
    listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen.bind((HOST, PORT))
    listen.listen(5)
    print('Serving HTTP on port %s ...' % PORT)
    threadPool = ThreadPoolExecutor(max_workers = MAX_WORKER, thread_name_prefix = "test_")
    while True:
        client_connection, client_address = listen.accept()
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        future = threadPool.submit(handle_connection, client_connection, client_address, current_time)
    threadPool.shutdown(wait = True)
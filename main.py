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

#不会被拉黑的状态码
safe_code = [200]
#黑名单
black_mutex = threading.Lock()
black_list = set()
#错误请求计数
error_mutex = threading.Lock()
error_count = dict()
#内存池
mem_pool_mutex = threading.Lock()
mem_pool = dict()

#从请求中读取文件路径
def read_request(request):
    first = request.find(' ')
    second = request.find(' ', first + 1)
    return request[:first], request[first + 1:second]
#检查是否有返回上层操作
def safe_check(file_path):
    if file_path.find('/..') >= 0:
        return False
    else:
        return True

def get_time():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def get_day():
    return time.localtime().tm_yday
#处理请求函数
def handle_connection(client_connection, client_address):
    current_time = get_time()
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

    code = 200
    #发送文件
    if safe_check(file_path):
        if file_path in mem_pool:
            http_response = mem_pool[file_path]
        else:
            try:
                f = open(ROOT + file_path,'rb')
                http_response = f.read()
                f.close()
                #放入内存池
                mem_pool_mutex.acquire()
                mem_pool[file_path] = http_response
                mem_pool_mutex.release()
            except:
                code = 404
                http_response = "HTTP/1.1 404 NOT FOUND".encode("utf-8")
    else:
        code = 403
        http_response = "HTTP/1.1 403 FORBIDDEN".encode("utf-8")

    if code not in safe_code:
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

    print(current_time + ' ' + str(code) + ' ' + client_address + ' ' + method  + ' ' + file_path)

    try:
        client_connection.sendall(http_response)
    except:
        print(current_time + ' BrokenPipe ' + client_address + ' ' + method  + ' ' + file_path)

    client_connection.close()

if __name__ == "__main__":
    listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen.bind((HOST, PORT))
    listen.listen(5)
    print('Serving HTTP on port %s ...' % PORT)
    while True:
        day = get_day()
        threadPool = ThreadPoolExecutor(max_workers = MAX_WORKER)
        while get_day() == day:
            client_connection, client_address = listen.accept()
            future = threadPool.submit(handle_connection, client_connection, client_address)
        print(get_time() + ' Restarting')
        threadPool.shutdown(wait = True)

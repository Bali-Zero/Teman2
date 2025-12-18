import socket


def check_port(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        try:
            s.connect((host, port))
            return True
        except (ConnectionRefusedError, socket.timeout):
            return False


if __name__ == "__main__":
    host = "localhost"
    port = 6333
    if check_port(host, port):
        print(f"Port {port} is OPEN. Qdrant might be running.")
    else:
        print(f"Port {port} is CLOSED. Qdrant is NOT running.")

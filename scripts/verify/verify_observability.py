import socket


def check_port(host, port, service_name):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        try:
            s.connect((host, port))
            print(f"✅ {service_name} ({port}): OPEN")
            return True
        except (ConnectionRefusedError, socket.timeout):
            print(f"❌ {service_name} ({port}): CLOSED")
            return False


if __name__ == "__main__":
    services = [
        ("Prometheus", 9090),
        ("Grafana", 3001),
        ("Jaeger UI", 16686),
        ("Backend Metrics", 8000),
        ("Qdrant", 6333),
    ]

    print("Verifying Observability Stack...")
    for name, port in services:
        check_port("localhost", port, name)

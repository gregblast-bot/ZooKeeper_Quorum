import subprocess
import sys
import time
import requests

# Runs the Docker container with the ZooKeeper services
def start_docker():
    print("\033[32mComposing Docker Environment...\033[0m")
    subprocess.run(["docker-compose", "up", "-d"], check=True)
    time.sleep(10) # Wait

# Shuts down the Docker container with the ZooKeeper services 
def stop_docker():
    print("\033[31mStopping Docker Environment...\033[0m")
    subprocess.run(["docker-compose", "down"], check=True)

# Run each instance asynchronously by using Popen
def start_server(host, port, zookeeper_ip, zookeeper_port):
    print(f"\033[32mStarting Server On {host}:{port}...\033[0m")
    server = subprocess.Popen(["python", "ZooKeeper_Quorum.py", "--host", host, "--port", port, "--zookeeper", zookeeper_ip, "--zookeeper_port", zookeeper_port])
    time.sleep(10) # Wait for server to start
    return port, server

# Terminate each instance and wait for them to finish                      
def stop_server(process):
    print("\033[31mStopping Server...\033[0m")
    process.terminate()
    process.wait()

# Send request and print add_update response
def add_update(host, port, key, value):
    url = f"http://{host}:{port}/update"
    response = requests.post(url, json={"key": key, "value": value})
    print(f"\033[34mAdd/Update response: {response.json()}\033[0m")

# Send request and print read_key response
def read_key(host, port, key):
    url = f"http://{host}:{port}/read"
    response = requests.get(url, params={"key": key})
    print(f"\033[34mRead response: {response.json()}\033[0m")

# Send request and print kill response
def kill(host, port):
    url = f"http://{host}:{port}/kill"
    response = requests.get(url)
    print(f"\033[34mKill response: {response.json()}\033[0m")
    return response.json()

# Send request and print timeout response
def timeout(host, port):
    url = f"http://{host}:{port}/timeout"
    response = requests.get(url)
    print(f"\033[34mTimeout response: {response.json()}\033[0m")
    return response.json()

# Main method
def main():
    zookeeper_ip = "127.0.0.1"
    zookeeper_port = "21811"
    host = "127.0.0.1"
    ports = ["5000", "5001", "5002"]
    #ports = ["5000", "5001", "5002", "5003", "5004", "5005", "5006", "5007", "5008"]

    try:
        start_docker()

        servers = [start_server(host, port, zookeeper_ip, zookeeper_port) for port in ports]

        print("\033[32mTesting Add and Read...\033[0m")
        # All updates routed through server on the elected leader. Sending through port 5000 as default.
        add_update(host, ports[0], f"key0", f"value0")

        #time.sleep(10) # Wait for testing

        for i in range(len(ports)):
            for j in range(len(ports)):
                print(f"\033[36mFor Port: {ports[i]}\033[0m")
                read_key(host, ports[i], f"key{j}") # Check existing keys on all ports

        #time.sleep(10) # Wait for testing

        print("\033[32mTesting Add and Read Through Replicas...\033[0m")
        # All updates routed through server on the elected leader. Sending through port 5002.
        add_update(host, ports[2], f"key2", f"value2")

        #time.sleep(10) # Wait for testing

        for i in range(len(ports)):
            for j in range(len(ports)):
                print(f"\033[36mFor Port: {ports[i]}\033[0m")
                read_key(host, ports[i], f"key{j}") # Check existing keys on all ports

        #time.sleep(10) # Wait for testing

        killReplica = False
        for port, server in servers:
            response = kill(host, port)
            is_leader = response.get("is_leader", False)
            if not is_leader:
                print("\033[32mTesting Replica Restore...\033[0m")
                print("\033[31mKilling a replica.\033[0m")
                stop_server(server)
                killReplica = True
                start_server(host, port, zookeeper_ip, zookeeper_port)
                print("\033[33mReading from replica.\033[0m")
                read_key(host, port, f"key0") # Read from killed replica before data restored
                read_key(host, port, f"key1") # Read from killed replica before data restored
                read_key(host, port, f"key2") # Read from killed replica before data restored
                time.sleep(20) # Wait for server to update
                read_key(host, port, f"key0") # Read from killed replica after data restored
                read_key(host, port, f"key1") # Read from killed replica after data restored
                read_key(host, port, f"key2") # Read from killed replica after data restored

        for port, server in servers:
            response = kill(host, port)
            is_leader = response.get("is_leader", False)
            if is_leader:
                print("\033[32mTesting Leader Election...\033[0m")
                print("\033[31mKilling the leader, electing a new one.\033[0m")
                stop_server(server)
                time.sleep(30)  # Wait for new leader election
                start_server(host, port, zookeeper_ip, zookeeper_port)
                print("\033[32mTesting Timeout Logic...\033[0m")
                timeout(host, port) # Enable server timeout.

        print("\033[32mTesting Stale Read...\033[0m")
        for i in range(len(ports)):
            for j in range(len(ports)):
                print(f"\033[36mFor Port: {ports[i]}\033[0m")
                read_key(host, ports[i], f"key{j}") # Check existing keys on all ports, old leader shoud be empty
        time.sleep(10)
        for i in range(len(ports)):
            add_update(host, ports[i], f"key{i}", f"value{i}") # All updates routed through server on some elected leader, update all
        for i in range(len(ports)):
            for j in range(len(ports)):
                print(f"\033[36mFor Port: {ports[i]}\033[0m")
                read_key(host, ports[i], f"key{j}") # Check existing keys on all ports

    # Handle an exception, so many exceptions... :/
    except Exception as e:
        print(f"Exception: {e}")

    finally:
        for _, server in servers:
            stop_server(server)
        stop_docker()

# Main method
if __name__ == "__main__":
    main()
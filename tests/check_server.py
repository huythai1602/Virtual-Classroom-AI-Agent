
import subprocess
import time
import requests
import sys
import os
import signal

def check_server():
    print("🚀 Starting server locally for verification...")
    # Start process
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8001"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.getcwd(),
        env=os.environ.copy()
    )
    
    print(f"Process started with PID {proc.pid}. Waiting for startup (10s)...")
    
    # Wait loop
    health_url = "http://127.0.0.1:8001/health"
    success = False
    
    try:
        for i in range(10):
            time.sleep(2)
            if proc.poll() is not None:
                print("❌ Process exited unexpectedly!")
                stdout, stderr = proc.communicate()
                print("STDOUT:", stdout.decode())
                print("STDERR:", stderr.decode())
                return False
                
            try:
                resp = requests.get(health_url, timeout=2)
                if resp.status_code == 200:
                    print(f"✅ Health check passed! Status: {resp.status_code}")
                    print(f"Response: {resp.json()}")
                    success = True
                    break
            except Exception as e:
                print(f"Attempt {i+1}: Connection failed ({e})")
                
    finally:
        print("Stopping server...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except:
            proc.kill()
            
    if success:
        print("\n🎉 Server verification SUCCESSFUL")
        return True
    else:
        print("\n❌ Server verification FAILED")
        return False

if __name__ == "__main__":
    if check_server():
        sys.exit(0)
    else:
        sys.exit(1)

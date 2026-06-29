"""获取公网IP"""
import requests

def get_public_ip():
    """获取公网IP"""
    try:
        response = requests.get('https://api.ipify.org?format=text', timeout=5)
        return response.text.strip()
    except:
        try:
            response = requests.get('https://icanhazip.com', timeout=5)
            return response.text.strip()
        except:
            return None

if __name__ == "__main__":
    ip = get_public_ip()
    if ip:
        print(f"您的公网IP: {ip}")
    else:
        print("无法获取公网IP")
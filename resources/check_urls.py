import re
import requests
import sys

def check_urls(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # regex to find urls
    urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', content)
    
    print(f"Found {len(urls)} URLs. Checking validity...")
    
    broken = []
    for url in urls:
        # cleanup markdown trailing chars
        url = url.rstrip(')')
        try:
            r = requests.head(url, timeout=5)
            if r.status_code >= 400:
                # try get
                r = requests.get(url, timeout=5)
                if r.status_code >= 400:
                    print(f"[FAIL] {url} -> {r.status_code}")
                    broken.append(url)
                else:
                    print(f"[OK] {url}")
            else:
                print(f"[OK] {url}")
        except Exception as e:
            print(f"[ERR] {url} -> {e}")
            broken.append(url)

    if broken:
        print(f"\nFound {len(broken)} broken URLs.")
        sys.exit(1)
    else:
        print("\nAll URLs are valid.")
        sys.exit(0)

if __name__ == "__main__":
    check_urls(r'd:\Projects\AI_POCs\TriArchitect-Agent\resources\paper\main.md')

import os
from pathlib import Path
from urllib import request


def get_maafw_version():
    self_path = Path(__file__)
    requirements_path = self_path.parent.parent / "requirements.txt"

    with open(requirements_path, "r") as f:
        for line in f:
            if "maafw" in line:
                return line.split("==")[1].strip()

    raise ValueError(f"MaaFramework not found in {requirements_path}")


def get_proxy_url():
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if proxy:
        if proxy.startswith("http://"):
            proxy = proxy[7:]
        elif proxy.startswith("https://"):
            proxy = proxy[8:]
        elif "http" not in proxy and "://" in proxy:
            raise ValueError(f"Unknown proxy protocol: {proxy}")
    return proxy


def download(download_url: str, dest_path: str | Path, proxy_url: str | None = None):

    try:
        # 创建带有User-Agent的请求
        req = request.Request(
            download_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0"
            },
        )

        print(f"正在下载 {download_url} 到 {dest_path}...")
        if proxy_url:
            print(f"尝试使用本地代理 {proxy_url} 进行下载...")
            # 设置代理处理器
            proxy_handler = request.ProxyHandler(
                {"http": f"http://{proxy_url}", "https": f"http://{proxy_url}"}
            )
            opener = request.build_opener(proxy_handler)

            # 使用带代理的opener发送请求
            response = opener.open(req)
        else:
            response = request.urlopen(req)

        # 获取文件大小（如果可用）
        total_size = int(response.headers.get("Content-Length", 0))
        print(f"Total size: {total_size / 1024 / 1024:.2f} MB")

        with open(dest_path, "wb") as out_file:
            downloaded = 0
            chunk_size = 8192
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                # 使用 \r 动态更新显示，而不是添加新行
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(
                        f"\rDownloaded: {downloaded / 1024 / 1024:.2f}/{total_size / 1024 / 1024:.2f} MB ({percent:.1f}%)",
                        end="",
                        flush=True,
                    )
                else:
                    print(
                        f"\rDownloaded: {downloaded / 1024 / 1024:.2f} MB",
                        end="",
                        flush=True,
                    )
            print()  # 下载完成后换行

        return True  # 成功下载
    except Exception as e:
        print(f"下载失败: {e}")
        return False

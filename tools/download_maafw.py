from pathlib import Path
import zipfile
import sys


from utils import get_maafw_version, get_proxy_url, download

sys.path.insert(0, Path(__file__).parent.__str__())
sys.path.insert(0, (Path(__file__).parent / "ci").__str__())

program_dir = Path(__file__).parent.parent

ghproxy = "https://gh-proxy.natsuu.top/"
version = "v" + get_maafw_version()
download_url = (
    "https://github.com/MaaXYZ/MaaFramework/releases/download/"
    + version
    + f"/MAA-win-x86_64-{version}.zip"
)


def download_with_proxy_or_mirror(download_url, dest_path):
    """尝试使用本地代理下载，失败后回退到镜像站或直接下载"""
    # 首先尝试使用本地代理
    if get_proxy_url():
        if download(download_url, dest_path, get_proxy_url()):
            return True

    # 如果代理下载失败，则尝试使用镜像站
    if download(ghproxy + download_url, dest_path):
        return True

    # 如果镜像站也失败，则尝试直接下载
    if download(download_url, dest_path):
        return True

    # 所有方式都失败
    print("所有下载方式都失败了")
    return False


def main():
    print("MaaFramework版本：" + version)

    Path("temp").mkdir(parents=True, exist_ok=True)
    dest_path = f"temp/MAA-win-x86_64-{version}.zip"

    print(f"Downloading from {download_url} to {dest_path}")

    # 尝试下载，优先使用本地代理，然后是镜像站，最后是直接下载
    success = download_with_proxy_or_mirror(download_url, dest_path)

    if not success:
        print("maafw下载失败，请阅读开发文档。手动下载并解压maafw到deps文件夹下")
        sys.exit(1)

    print("Download completed.")

    print(f"Extracting {dest_path}...")
    with zipfile.ZipFile(dest_path, "r") as zip_ref:
        extract_path = program_dir / "deps"
        # 解压时跳过schema.json文件
        for member in zip_ref.infolist():
            if member.filename.endswith("schema.json"):
                print(f"跳过文件: {member.filename}")
                continue
            zip_ref.extract(member, extract_path)
        print(f"Extracted to {extract_path}.")

    Path(dest_path).unlink()  # Remove the zip file after extraction


if __name__ == "__main__":
    main()

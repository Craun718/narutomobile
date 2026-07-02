import urllib.request
import zipfile

from utils import assets_dir

OCR_DOWNLOAD_URL = (
    "https://download.maafw.xyz/MaaCommonAssets/OCR/ppocr_v6/ppocr_v6-small.zip"
)


def configure_ocr_model():
    ocr_dir = assets_dir / "resource" / "base" / "model" / "ocr"

    if ocr_dir.exists():
        print("Found existing OCR directory, skipping download.")
        return

    print(f"Downloading OCR model from {OCR_DOWNLOAD_URL}...")
    ocr_dir.mkdir(parents=True, exist_ok=True)

    zip_path = assets_dir / "resource" / "base" / "model" / "ocr.zip"
    urllib.request.urlretrieve(OCR_DOWNLOAD_URL, zip_path)

    print("Extracting OCR model...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(ocr_dir)

    zip_path.unlink()
    print("OCR model configured successfully.")


if __name__ == "__main__":
    configure_ocr_model()
    print("OCR model configured.")

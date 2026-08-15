# Android 客户端

外壳是 [MaaFwApp](https://github.com/Aliothmoon/MaaFwApp) 子模块。
`interface.json` 在 `assets/`，agent 在仓库根，Gradle 只能从一个目录 include，所以先摊成 `Android/pi-root/`。

## 首次

```bash
git submodule update --init Android/MaaFwApp
python tools/prepare_android_pi.py
python Android/MaaFwApp/scripts/setup_maa_framework.py --abi arm64-v8a --tag v5.12.3
python Android/MaaFwApp/scripts/build_agent_bundle.py --out Android/agent-dist \
    --requirements requirements.txt \
    --exclude pillow --exclude win32-setctime --exclude colorama --exclude jeepney \
    --require pillow==11.0.0 --extra-index-url https://chaquo.com/pypi-13.1/
```

`prepare_android_pi.py` 会顺带拉 OCR（`tools/ci/configure.py`），没有模型识别会空转。

在 `Android/MaaFwApp/local.properties` 里写（子模块自己的，不进 git）：

```properties
sdk.dir=<Android SDK>
pi.profile=../profile.yaml
build.debugAbi=arm64-v8a
```

## 出包

```bash
# 改了 assets / agent 源码
python tools/prepare_android_pi.py

# 已连接设备
./Android/MaaFwApp/gradlew.bat -p Android/MaaFwApp :app:installDebug

# 正式包：release 固定打 arm64-v8a + x86_64，so 也要两个 ABI
python Android/MaaFwApp/scripts/setup_maa_framework.py --tag v5.12.3
./Android/MaaFwApp/gradlew.bat -p Android/MaaFwApp :app:assembleRelease
```

包名是 `com.aliothmoon.maafw.man`。桌面端的 `child_exec` 不参与，解释器是配方里的 `bin/python3`。

签名读环境变量，缺了就打未签名包：`KEYSTORE_PATH`、`KEYSTORE_PASSWORD`、`KEY_ALIAS`、`KEY_PASSWORD`。也可写进子模块的 `local.properties`，环境变量优先。

CI：

- `.github/workflows/android.yml`：改相关路径就打 debug 包
- `.github/workflows/android-release.yml`：打 `v*` 或手动触发时打 release；有签名 secrets 就签名，APK 挂 artifact，tag 还会附到 GitHub Release

仓库 Secrets（release）：`ANDROID_KEYSTORE_BASE64`（keystore 的 base64）、`KEYSTORE_PASSWORD`、`KEY_ALIAS`、`KEY_PASSWORD`。

`pi-root/` 和 `agent-dist/` 不进 git。升外壳：

```bash
git -C Android/MaaFwApp fetch
git -C Android/MaaFwApp checkout origin/main
git add Android/MaaFwApp
```

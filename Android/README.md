# Android 客户端

外壳是 [MaaFwApp](https://github.com/Aliothmoon/MaaFwApp) 子模块，和本仓库的开发用 MaaFwApp 不是同一份。
`interface.json` 在 `assets/`，agent 在仓库根，Gradle 只能从一个目录 include，所以先摊成 `Android/pi-root/`。

## 首次

```bash
git submodule update --init Android/MaaFwApp
python tools/prepare_android_pi.py
python Android/MaaFwApp/scripts/setup_maa_framework.py --abi arm64-v8a
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
```

包名是 `com.aliothmoon.maafw.maanaruto`。桌面端的 `child_exec` 不参与，解释器是配方里的 `bin/python3`。

CI：`.github/workflows/android.yml` 按上面那套打 debug 包，APK 挂在 Actions artifact 上。

`pi-root/` 和 `agent-dist/` 不进 git。升外壳：

```bash
git -C Android/MaaFwApp fetch
git -C Android/MaaFwApp checkout origin/main
git add Android/MaaFwApp
```

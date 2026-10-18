# 律吕调音器 (LvLv ProTuner)

<p align="center">
  <img src="android/app/src/main/res/drawable/ic_launcher.png" width="120" height="120" alt="LvLv ProTuner Icon" />
</p>

**律吕 ProTuner** 是一款专为东西方弦乐与民乐（二胡、古筝、琵琶、古琴、中阮、柳琴、吉他、小提琴、大提琴、尤克里里、贝斯及十二平均律）打造的 高精防抖调音器，支持 Android 原生安装与 Web 离线运行。

---

## ✨ 核心特性 (Key Features)

1. **🎻 二胡与弓弦乐器专属防抖引擎 (Anti-Jitter DSP Engine)**
   - **亚音分自相关基频提取 (McLeod / NSDF + 抛物线插值)**：有效抑制二胡内弦（D4）强二次谐波造成的八度跳变。
   - **五阶中值滤波 + 280ms 揉弦周期积分**：剔除运弓换向瞬间的擦弦噪波，自动锁定 5–7Hz 揉弦的中心音高。
   - **±35 音分弦位迟滞锁定 + 5Hz 数字防闪烁节流 + 1.6 秒余音保持**：彻底告别传统调音器指针“抖一抖”和数字乱跳的问题。

2. **🍎 极简直观的 Apple 设计语言与零跳动布局 (Zero-Layout-Shift UI)**
   - 采用纯内联像素级定高三段式界面（顶部乐器栏 + 中央圆弧指针表盘 + 底部琴弦与拾音坞），无任何外部 CDN 依赖。
   - 在 Android 底层（`classes.dex`）锁定竖屏方向（`SCREEN_ORIENTATION_PORTRAIT`）、屏幕常亮（`FLAG_KEEP_SCREEN_ON`）与 100% 字号缩放（`setTextZoom(100)`），杜绝系统大字号或异步重绘引起的界面跳动。
   - 点击中央超大音名即可一键切换 **音名 (`D4`) / 简谱 (`1`) / 唱名 (`Re`)**。

3. **⭐ 中西乐器库、星标收藏与自定义排序**
   - 内置 **二胡**（标准 D4-A4 / 二泉 G3-D4 / C调 C4-G4）、**21 弦古筝**（含 3/8/13/18 绿弦标记）、**琵琶**、**古琴**、**中阮/柳琴**、**吉他**、**小提琴**、**大提琴/中提琴**、**尤克里里**、**贝斯** 与 **十二平均律全音域**。
   - 支持一键星标收藏（`★`）、自定义上下排序与置顶、以及新建任意自定义定弦乐器。

---

## 📂 项目目录结构 (Project Structure)

```text
lvlv-protuner/
├── android/
│   └── app/src/main/
│       ├── AndroidManifest.xml
│       ├── assets/
│       │   └── index.html               # 零外部依赖的内联高精防抖调音前端
│       ├── java/com/lvlv/protuner/
│       │   ├── MainActivity.java        # 安卓原生窗口锁定、权限请求与宿主容器
│       │   └── TunerChromeClient.java   # WebAudio 麦克风流自动授权桥接
│       └── res/drawable/
│           └── ic_launcher.png          # 256x256 超采样抗锯齿应用图标
├── scripts/
│   └── build_apk.py                     # 纯 Python 零 SDK 依赖的 APK 编译器 (DEX + AXML + ARSC + V1/V2 双签名)
├── releases/
│   └── LvLv_ProTuner_v2.0.apk           # 已编译并签名的 Android 可直接安装 APK
├── .github/workflows/
│   └── release-apk.yml                  # GitHub Actions 自动编译与发布流水线
├── push_to_github.sh                    # macOS / Linux 一键推送至 GitHub 脚本
├── push_to_github.bat                   # Windows 一键推送至 GitHub 脚本
├── LICENSE                              # MIT 开源协议
└── README.md
```

---

## 🚀 快速编译与运行 (Build & Run)

### 方式一：直接安装已编译的 APK
前往 [`releases/LvLv_ProTuner_v2.0.apk`](releases/LvLv_ProTuner_v2.0.apk) 下载并发送至 Android 手机（Android 6.0 ~ Android 15）直接安装。

### 方式二：使用纯 Python 编译器一键重新构建 APK
本项目内置了从底层直接生成 Dalvik 字节码（`classes.dex`）、二进制清单（`AndroidManifest.xml`）、资源表（`resources.arsc`）并完成 **4 字节对齐 + V1 (JAR PKCS#7) + V2 (`APK Sig Block 42`) 双重签名**的编译器，无需安装庞大的 Android Studio：

```bash
pip install pillow cryptography
python3 scripts/build_apk.py
```

---

## 📄 开源协议 (License)
本项目基于 [MIT License](LICENSE) 开源。

# 律吕调音器 (LvLv ProTuner)

<p align="center">
  <img src="android/app/src/main/res/drawable/ic_launcher.png" width="120" height="120" alt="LvLv ProTuner Icon" />
</p>

律吕 ProTuner 是一款使用麦克风检测单音音高的调音器，提供 Android APK 和基于 Web Audio 的单文件前端。支持中西弦乐预设、自动识弦、手动锁弦、参考音和 Anti-Jitter DSP 稳音处理。

本文依据仓库源码、仓库内 APK 和构建工作流编写。功能实现不等同于精度或设备兼容性测试结论；已知范围与限制见下文。

## 安装与启动

### Android：下载现成 APK

**[直接下载 LvLv_ProTuner_v2.0.apk](https://raw.githubusercontent.com/RuleLight/instruments_tunner/main/releases/LvLv_ProTuner_v2.0.apk)** · [查看仓库内 APK](releases/LvLv_ProTuner_v2.0.apk)

1. 在 Android 设备上下载 APK，或从电脑传到手机后打开。
2. 如果系统提示禁止安装，按系统提示为实际打开 APK 的浏览器或文件管理器允许“安装未知应用”，再返回安装。
3. 打开“律吕调音器”，允许麦克风权限。
4. 点击底部“开启麦克风调音”；按钮变为“正在拾音 · 请拉奏或拨弦”后，拨弦或拉奏单个音。

清单与 APK 构建器均声明最低 API 23（Android 6.0）、目标 API 29。最低版本声明不代表已完成 Android 6–15 的全版本真机验证；音频功能还依赖设备的 WebView 与麦克风能力。

当前仓库内 APK 的 SHA-256：

```text
9d02f8ccbdc55448b77bdaa9913af5cf60b3f5615b947359e912055be41ba28b
```

此校验值仅对应本次核对的仓库 APK；自行重新构建后的文件会不同。

### Web：本地运行前端

前端位于 [android/app/src/main/assets/index.html](android/app/src/main/assets/index.html)，样式与脚本内联，无外部 CDN 依赖。可在支持 Web Audio、AudioContext 和 getUserMedia 的浏览器中使用。

在本机仓库根目录运行：

```bash
python3 -m http.server 8000 --bind 127.0.0.1 --directory android/app/src/main/assets
```

随后在**同一台电脑**打开 <http://localhost:8000>，点击“开启麦克风调音”并授权。远程部署请使用 HTTPS；直接双击 HTML 或通过普通局域网 HTTP 打开时，麦克风能否使用取决于浏览器的安全上下文限制，不能保证可用。

Android 加载的是 APK 内的本地页面，调音逻辑无需外部 CDN。仓库未提供 Service Worker 或可安装 PWA 的配置，不应将单文件前端等同于已验证的离线网站安装方案。

## 使用说明

### 选择乐器与调音

1. 点击左上角乐器名称，选择乐器；在底部下拉框选择定弦预设。
2. 使用“自动识弦”按检测结果匹配当前预设中的目标弦。若要固定调某根弦，先切换到“手动锁弦”，再点击下方对应琴弦。
3. 开启麦克风，每次拨弦或拉奏一个音，查看指针与音分读数。负值表示偏低，正值表示偏高；界面在平滑后偏差绝对值不大于 4.5 音分时显示绿色“音准完美”。这是界面的判定阈值，并非测量精度保证。
4. 再次点击拾音按钮可停止麦克风。点击“听标准音”播放所选弦的参考音，再次点击停止；参考音和麦克风拾音互斥，开启其中一个会停止另一个。

默认首次状态为二胡、标准 D4–A4、自动识弦、A4 = 440 Hz、强稳音。读取到本地设置时，部分选项会恢复。

### 常用设置

| 控件 | 行为 |
| --- | --- |
| 顶部频率按钮 | 依次切换 A4：440 → 442 → 444 → 432 → 438 Hz，改变目标频率与参考音 |
| “稳音”按钮 | 在“强(二胡) / 均衡 / 灵敏”之间切换；对应平滑窗口为 280 / 160 / 70 ms |
| 中央大音名 | 切换音名、简谱、唱名 |
| ◐ | 切换深浅色界面 |
| 乐器列表中的 ★ | 收藏或取消收藏，可在“★ 收藏”分类查看 |
| 乐器列表中的“排序” | 显示置顶、上移和下移操作 |

**记谱说明：** 当前简谱与唱名按固定音级映射（C = 1 / Do，D = 2 / Re，A = 6 / La），不是随乐器定弦变化的首调简谱，也没有单独的调号选择功能。

### 自定义定弦与保存

打开乐器列表 → “+ 自定义”，输入名称及以**英文逗号**分隔的音名，如：

```text
G4, D5
C3, F#3, Bb3
```

每个音名格式为 A–G、可选的 `#` 或小写 `b`、一位八度数字；点击“保存并选用”。程序会忽略不符合格式的音名；名称为空或没有有效音名时不会保存。格式允许输入不代表该音高在检测范围内。

乐器库（含收藏、排序、自定义定弦）、当前乐器、A4 基准、记谱方式和主题使用 localStorage 保存。当前代码不保存预设索引、所选弦、自动/手动模式或手动选择的稳音档位；清除应用或浏览器站点数据后，本地配置可能丢失。界面未提供配置导入导出及自定义乐器编辑、删除入口。

## 已实现的功能

### 内置乐器与定弦

以下顺序与源码中的各预设琴弦顺序一致。

| 乐器 | 定弦预设 |
| --- | --- |
| 二胡 | 标准 D4–A4；二泉 G3–D4；C 调 C4–G4 |
| 六弦吉他 | 标准 E2–A2–D3–G3–B3–E4；Drop D：D2–A2–D3–G3–B3–E4 |
| 21 弦古筝 | D 调五声，从 21 弦 D2 至 1 弦 D6；标记 18、13、8、3 弦为绿弦 |
| 小提琴 | G3–D4–A4–E5 |
| 琵琶 | A2–D3–E3–A3 |
| 尤克里里 | G4–C4–E4–A4（高 G） |
| 古琴 | 正调 F 调：C2–D2–F2–G2–A2–C3–D3 |
| 中阮 / 柳琴 | 中阮 G2–D3–G3–D4；柳琴 G3–D4–G4–D5 |
| 大提琴 / 中提琴 | 大提琴 C2–G2–D3–A3；中提琴 C3–G3–D4–A4 |
| 四弦贝斯 | E1–A1–D2–G2 |
| 十二平均律 | 自动识弦模式按最近半音选择目标；手动模式提供 C4、D4、E4、F4、G4、A4、B4 |

### Anti-Jitter DSP 与界面

- 使用 NSDF 自相关及抛物线插值提取音高。
- 使用最多 5 帧中值滤波、分档时间窗平均和指数平滑处理音分偏差。
- 自动识弦时为当前弦提供 35 音分的匹配距离优待，以减少弦位切换；这不是测量误差范围。
- 普通数字读数更新间隔至少为 180 ms；无有效信号后约 1.6 秒清除保持的读数。
- Android 宿主设置竖屏、屏幕常亮与 WebView 字号缩放 100%；前端采用固定区域布局。

这些机制旨在减少读数抖动。仓库未附精度、延迟、抗噪或八度误判率的测量报告，因此不承诺“亚音分精度”“完全消除八度跳变”或特定揉弦频率下的效果。

## 范围、读数与排查

- **并非无限音域：** 音高提取的周期搜索约对应 36–1500 Hz，主循环只接受 35–1500 Hz。实际可用范围还受采样率、输入缓冲区、信号强度及麦克风影响。“十二平均律全音域”是界面名称，不代表覆盖所有八度。
- **古筝高音弦限制：** 在默认 A4 = 440 Hz 时，预设 B5、D6 超过 1500 Hz 的检测上限。存在这些目标弦和参考音，不代表能正确拾取其基频。
- **频率经过处理：** 界面“实测 Hz”由平滑后的音分反算；处理前的音分偏差被截断到 ±50。它不是未经处理的原始频率，偏差很大时也不能据此判断真实偏差大小。
- **没有读数：** 确认按钮已显示“正在拾音”，检查系统或浏览器的麦克风权限，并确认输入为单音且音量足够。代码会拒绝较弱信号（RMS < 0.008）及不满足相关峰阈值的帧。
- **点拾音后仍回到待机：** 当前代码捕获麦克风错误后不显示具体原因。检查权限与 Web 运行地址；Android 若首次授权后仍未启动，可再次点击拾音按钮。
- **识弦不稳定或指针过慢：** 可固定目标弦，或切换稳音档位；强稳音使用更长的平均窗口，灵敏档窗口更短。

## 版本与发布状态

| 项目 | 当前材料中的值 |
| --- | --- |
| 首次开源提交 | 2026-10-18，[`1e372c9`](https://github.com/RuleLight/instruments_tunner/commit/1e372c92f4832105c12b51f9dd9d9d833adf642e) |
| 产品与 APK 文件名版本 | v2.0 / `LvLv_ProTuner_v2.0.apk` |
| Android versionName / versionCode | `2.0.0` / `2` |
| Android 包名 | `com.lvlv.protuner` |
| 分发文件 | 仓库 `releases/` 目录下的 APK；本次核对时没有 GitHub Release 条目 |

[release-apk.yml](.github/workflows/release-apk.yml) 在推送到 main/master、推送 `v*` 标签或手动触发时构建 APK，并上传名为 `LvLv_ProTuner_v2.0_APK` 的 Actions artifact。**该工作流没有创建 GitHub Release 或上传 Release asset 的步骤**；目录名 `releases/` 与 GitHub Releases 页面是不同概念。

## 从源码构建 Android APK

在 Python 3 环境中构建；现有 Actions 配置使用 Python 3.11。无需 Android Studio 或 Android SDK。

```bash
git clone https://github.com/RuleLight/instruments_tunner.git
cd instruments_tunner
python3 -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell 改用：.venv\Scripts\Activate.ps1
python -m pip install pillow cryptography
python scripts/build_apk.py
```

输出为 `releases/LvLv_ProTuner_v2.0.apk`；脚本也会重新生成并写入应用图标。

构建器直接生成 DEX、二进制 AndroidManifest 与资源表，打包 HTML，并生成 V1/V2 签名。**它不会编译目录中的 Java 文件，也不会读取文本 AndroidManifest.xml 生成清单**；修改宿主行为或包名/版本/SDK 声明时，必须同步检查构建脚本内的生成逻辑。

**重建与安装注意：** 脚本每次生成新的 RSA 签名密钥与证书，未读取持久化发布密钥。因此不同构建的 APK 签名会变化，不能保证覆盖安装已有同包名版本；如需卸载后安装，应先记录自定义定弦等本地数据。现有构建不保证逐字节可复现。

## 项目结构

```text
instruments_tunner/
├── android/app/src/main/
│   ├── AndroidManifest.xml            # 可读清单；构建脚本另行生成二进制清单
│   ├── assets/index.html              # 调音界面、音高检测、DSP 与本地配置
│   ├── java/com/lvlv/protuner/
│   │   ├── MainActivity.java          # 可读 Android 宿主实现
│   │   └── TunerChromeClient.java     # WebView 权限桥接
│   └── res/drawable/ic_launcher.png
├── scripts/build_apk.py               # APK 生成、打包与签名
├── releases/LvLv_ProTuner_v2.0.apk
├── .github/workflows/release-apk.yml   # 构建并上传 Actions artifact
├── push_to_github.sh
├── push_to_github.bat
├── LICENSE
└── README.md
```

## 仍需维护者提供的信息

以下内容无法仅依据现有代码和发布材料补齐：

- **兼容性实测记录：** 测试过的机型、Android/WebView 版本、浏览器版本，以及安装、授权、拾音与参考音结果。
- **DSP 验证材料：** 测试音源与条件、各音域误差、延迟、噪声及强谐波/揉弦条件下的表现；如有高音弦实测，也请提供。
- **后续版本与分发安排：** 是否维护正式 GitHub Releases、版本变更记录，以及后续 APK 是否采用稳定签名以支持覆盖升级。
- **面向用户的反馈渠道：** 维护者希望公开的联系方式或其他反馈入口。

## 开源协议

本项目基于 [MIT License](LICENSE) 开源。

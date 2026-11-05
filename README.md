# 一二布布桌面宠物（Python 复刻版）

将 Windows 上的 C#/WPF 桌面宠物 **YierPet4Win** 用 Python 完整复刻，并在原版基础上
新增了三项优化功能。沿用原版的全部美术素材（`Assets/`），保持四种形象与原有手感。

## 运行环境

- Windows 10/11（透明置顶悬浮窗依赖 Windows 桌面）
- Python 3.10+
- 依赖：`PyQt6`、`Pillow`、`psutil`

```bash
pip install -r requirements.txt
python main.py
```

> 本项目自带 `.venv`（已装好依赖），可直接用 PyCharm 打开运行；
> 或使用 `.\.venv\Scripts\python.exe main.py`。

## 已复刻的原版能力

| 能力 | 说明 |
| --- | --- |
| 桌面悬浮 | 无边框透明窗口、置顶、不出现在任务栏 |
| 四种形象 | 经典一二（精灵图集）/ 活力一二 / 活力布布 / 一二布布合体（PNG 帧序列） |
| 9 种动画 | 待机 / 跑 / 挥手 / 跳跃 / 沮丧 / 等待 / 工作中 / 审阅 / 拖拽奔跑 |
| 自主行为 | 随机散步、跳跃、挥手；贴边掉头 |
| 气泡说话 | 头顶圆角气泡，语料随机 |
| 健康提醒 | 久坐 / 喝水 / 深夜关怀 / 摸鱼（可单独开关） |
| 系统哨兵 | CPU 红温 / 内存压力 / 电量 / 磁盘（可单独开关） |
| 陪伴模式 | 早晨 / 午饭 / 下午咖啡 / 周五撒欢 / 编码久战 |
| 抛掷物理 | 拖甩、重力、反弹；摔狠了生气 |
| 右键菜单 | 形象 / 动作 / 随机开关 / 提醒开关 / 退出 / `Alt+右键` 测试提醒 |

素材契约与 mac/win 原版一致：经典形象为 `Assets/spritesheet.webp`（8 列 × 9 行，
每格 192×208）；贴纸包为 `Assets/Packs/{yier,bubu,duo}/<id>/frame_*.png` + `meta.json`。
设置保存在 `%AppData%/YierBubu/settings.json`。

## 新增优化功能

### 1. 鼠标跟随奔跑（可开关）
- 右键菜单新增「开启/关闭鼠标跟随」。
- 开启后，宠物会以「奔跑」动画自动追着鼠标光标移动，沿鼠标轨迹运动；
  水平方向自动判断朝左/朝右（贴纸角色会水平镜像）。
- 设置项 `mouse_follow`（默认关闭）可持久化。
- 跟随期间自动暂停随机行为；拖拽或抛掷时让位。

### 2. 修复「一二布布」拖拽时奔跑失效
- 原版中贴纸类形象（含「一二布布」）在拖拽时 `HandleDrag` 直接 return，导致无法奔跑；
  且「一二布布」每帧本来就同时包含「一二」与「布布」两个角色。
- 本版对所有形象（含贴纸/合体）实现拖拽奔跑：拖拽时窗口随光标移动，并循环播放
  「奔跑感」贴纸（优先 `exercise` → `happy` → `idle`）。
- 因此「一二布布」在拖拽时两个角色**同框同步奔跑**（即你要求的「最好情况」）。
  —— 由于合体素材天然是同帧双角色，无需也无需退而求其次「随机选一二或布布」，
  直接实现了两角色一起跑的最优解。

### 3. 提醒条件支持自定义
- 右键菜单新增「自定义提醒条件…」，打开设置对话框。
- 可逐项调整触发阈值与时段：
  - 健康类：久坐时长、喝水间隔、摸鱼判定与重复、离开判定；
  - 深夜关怀：起止小时、重复间隔；
  - 系统哨兵：CPU 阈值/连续次数/重复、内存警告与严重阈值、磁盘剩余阈值/重复；
  - 陪伴时段：早晨/午饭/下午/周五 的起止小时；
  - 其它：编码久战阈值、提醒最小间隔、散步速度、跟随速度。
- 另设「提醒开关」页，可单独开关 14 种提醒。
- 所有修改写入 `settings.json`，提醒中心下次判定即生效；支持「恢复默认」。

## 其它新增功能（音效 / 托盘 / 自启动 / 陪伴）

### 音效系统（可开关）
- 按**展示角色**播放对应语音（启动与右键/托盘菜单换装时自动播放）；
- 按**情绪状态**播放音效（生气 / 开心 / 难过），且按角色分开；
- **定时随机播放**：宠物偶尔自发说一句，更有陪伴感；
- 角色语音取自粉丝项目打包的真实一二/布布 语音；往 `Assets/Audio/<角色>/` 目录里
  添加更多 `.wav/.mp3` 即可扩充，无需改代码；情绪音效同理放 `mood_<心情>.*`；
- 仓库内置音频统一为 WAV/PCM，较长的几段语音已裁剪为前 6 秒，适合 `QSoundEffect`
  的低延迟短音效定位；若自行添加长音频，建议同样裁短或转码；
- 右键菜单 / 托盘菜单「音效」总开关控制一切（关闭即全静音）。

### 系统托盘 + 开机自启动
- 右下角系统托盘图标：左键显示/隐藏宠物，右键弹出与宠物右键一致的主菜单；
- 右键菜单新增「开机自启动」（写入 Windows 注册表 Run 项，非 Windows 自动降级）。

> 源码详见 `pet/audio.py`、`pet/tray.py`、`pet/autostart.py`。

## 项目结构

```
yierbubu/
├── main.py                  # 入口：加载素材、创建宠物与提醒中心
├── requirements.txt
├── Assets/                  # 原版美术素材（spritesheet.webp + Packs）
└── pet/
    ├── states.py            # 动画状态 / 帧时长 / 显示名
    ├── styles.py            # 形象枚举
    ├── config.py            # 设置持久化 + 可自定义提醒条件
    ├── sprites.py           # 图集切片 + 贴纸包加载
    ├── activity.py          # 输入空闲 / 前台进程 / 摸鱼检测（Windows）
    ├── systemmon.py         # CPU / 内存 / 电量 / 磁盘
    ├── reminders.py         # 提醒中心（14 种提醒 + 判定逻辑）
    ├── speech.py            # 头顶气泡窗口
    ├── pet_window.py        # 主窗口：动画/拖拽/抛掷/自主行为/三项优化/菜单
    ├── settings_dialog.py   # 自定义提醒条件对话框
    ├── audio.py             # 音效系统（QSoundEffect：按角色/情绪播放，可开关）
    ├── tray.py              # 系统托盘（右下角，显示/隐藏 + 菜单）
    └── autostart.py         # 开机自启动（Windows 注册表 Run 项）
```

## 与原版差异（实现层）

- 语言/框架：C# + WPF → Python + PyQt6（透明置顶窗口用 `Qt.Tool` +
  `FramelessWindowHint` + `WA_TranslucentBackground`）。
- 图片解码：ImageSharp(WebP) → Pillow。
- 系统指标：WMI/PerformanceCounter → psutil（跨平台，Windows 重点支持）。
- 输入空闲/前台进程：仍走 `user32` 的 `GetLastInputInfo` / `GetForegroundWindow`。
- 新增第 1、2、3 项优化（见上）。

## 下载（Windows 预编译，小白专用）

不想装 Python 环境的同学，可直接下载已打包好的 **Windows 64 位** 压缩包，解压后双击
`yierbubu.exe` 即可运行（绿色免安装，无需安装 Python）。

- 下载地址：<https://gitee.com/duan-zebing/yierbubu/raw/master/yierbubu-win.zip>
  （Gitee 对大于 50MB 的文件要求先登录账号才能下载；登录后点击即可正常下载，压缩包约 99MB）
- 内置音频：共 124 条 `.wav`，**不含 MP3**（全部走 `QSoundEffect` 原生 PCM 直读，
  避免 Qt FFmpeg 后端初始化日志与长音频加载卡顿）：
  - 四个角色目录 120 条：112 条粉丝项目真实原声（经典一二 / 活力一二 / 活力布布各 32 条，
    一二布布合体 16 条双语音）+ 8 条 `lalalal` / `omjnjjj` / `快睡觉` 语音
    （统一裁剪为**前 6 秒**，32kHz / 单声道 / 16bit PCM）；
  - 4 条全局情绪兜底音效 `mood_*.wav`。
- 解压后目录里的 `yierbubu.exe` 即主程序；首次运行若被系统/杀软误报，请允许或加白名单。
- 设置保存在 `%AppData%/YierBubu/settings.json`；卸载直接删除解压目录即可。

> 源码运行方式见上方「运行环境」。如需自行重新打包，仓库内含 `yierbubu.spec`，
> 执行 `pyinstaller yierbubu.spec --noconfirm --clean` 即可（需先 `pip install pyinstaller`）。

📚 使用指南
完整打包流程
打开 PyPacker → 看到首页 5 个功能卡片

基本设置

入口脚本：选择你要打包的 .py 文件

程序名称：自动填充为脚本名，可修改

输出目录：留空则在脚本旁生成 dist/

打包模式：

单文件 --onefile：适合小工具，只有一个 exe

文件夹 --onedir：适合大项目，启动快（推荐）

构建选项：按需勾选 --console / --clean / --noconfirm

图标

源图片：选一张 PNG / JPG

缩放方式：一般用「居中裁剪铺满」

手动裁剪：需要特殊构图时用

勾选「把图标嵌入目标程序」：让窗口和任务栏图标也变成你选的图

版本信息（仅 Windows）

填写文件版本、产品版本、公司名称、版权信息等

打包后右键 exe → 属性 → 详细信息，能看到这些内容

高级（可选）

附加数据：需要打包的图片、配置、字体等

隐藏导入：PIL._tkinter_finder、pkg_resources.py2_warn 之类

排除模块：matplotlib、numpy、test 等用不上的

UPX 目录：如果你装了 UPX

额外参数：想加什么 PyInstaller 参数都可以

点「开始打包」 → 自动切到日志页，进度条实时推进

打包完成后 → 会询问是否打开输出目录

配置管理
保存配置：把所有选项存成 .json

加载配置：下次打包同类项目直接加载

配置文件默认保存在用户目录下的 .pypacker.json，关闭时会自动保存当前状态。

关于图标嵌入
勾选「把图标嵌入目标程序」后，PyPacker 会：

生成一个包含 base64 ico 数据的 runtime hook 脚本

PyInstaller 打包时用 --runtime-hook 把它嵌进去

目标程序运行时，hook 会在主脚本执行之前自动：

把 base64 还原成 ico 文件

monkey-patch Tk() / QApplication() / wx.Frame() 等构造函数

窗口创建时自动设置图标

用户程序一行代码都不用改，就能让窗口、任务栏、exe 三者图标一致。

🗂 项目结构
text
PyPacker/
├── main.py                      # 启动入口
├── requirements.txt             # 依赖清单
├── README.md
├── LICENSE
└── pypacker/                    # 核心包
    ├── __init__.py
    ├── __main__.py              # 支持 python -m pypacker
    ├── constants.py             # 主题色、字体、页面元数据
    ├── utils.py                 # 通用工具（含子进程隐藏）
    ├── python_env.py            # 解释器解析 + PyInstaller 探测
    ├── icon.py                  # 图标处理 + 矢量图标绘制
    ├── icon_embed.py            # ⭐ base64 嵌入 + runtime hook 生成
    ├── version_info.py          # Windows 版本资源文件生成
    ├── config_io.py             # 配置读写
    ├── builder.py               # PyInstaller 命令构建 + 执行 + 进度解析
    ├── widgets.py               # 自定义控件 FeatureCard
    ├── crop_dialog.py           # 可视化裁剪对话框
    └── app.py                   # 主应用（UI 装配 + 事件处理）
模块职责
模块	职责
constants.py	集中管理颜色、字体、页面元数据，改主题只需动这一个文件
utils.py	颜色工具、版本解析、子进程隐藏（CREATE_NO_WINDOW）
python_env.py	智能解析可用的 Python 解释器 + 检测 PyInstaller
icon.py	图片 → ico 的转换逻辑，以及首页卡片的矢量图标
icon_embed.py	生成 runtime hook，把图标注入目标程序
version_info.py	生成 PyInstaller 的版本资源文件
builder.py	组装命令行、执行、解析进度
app.py	纯 UI 层，只负责展示和交互
❓ 常见问题
Q：打包出来的 exe 报 Tk data directory not found？
PyPacker 会自动加 --collect-all tkinter，理论上不会出现。如果还报，检查：

PyInstaller 版本是否 ≥ 6.0（pip install --upgrade pyinstaller）

是否在用 --onefile 模式，改 --onedir 试试

Q：退出时弹 "Failed to remove temporary directory"？
这是 --onefile 模式的固有问题（后台线程/子进程还占用文件）。切换到 --onedir 模式即可彻底解决。

Q：图标嵌入没生效？
确认打包时勾选了「把图标嵌入目标程序」

运行目标 exe，打开 %TEMP%\pypacker_icon_hook.log 看日志

日志里应该能看到 iconphoto 成功 或 WinAPI 设置成功

如果是 --onefile 模式，任务栏图标可能不生效（bootloader 持有任务栏图标），改 --onedir

Q：第二次打包为什么变快了？
PyPacker 会把 build 缓存放在脚本目录的 .pypacker_cache/ 里，第二次打包复用缓存跳过大量分析。想清缓存可以：

在 PyPacker 里勾选「打包前清理缓存 --clean」

直接删除 .pypacker_cache/ 目录

Q：能打包 macOS / Linux 吗？
可以打包，但：

版本信息 只在 Windows 生效（其他平台是 PE 资源，不适用）

图标嵌入 的 Windows API 部分不生效，但 tkinter / Qt / wx 的 patch 仍然有效

exe 后缀会变成平台对应的可执行文件

Q：打包后 exe 特别大？
几个方向：

在「高级」页用排除模块剔除用不上的库

用 UPX 压缩（下载 UPX，在「高级」页指定目录）

用 --onedir 模式，最终可压缩成 zip

Q：为什么 PyPacker 打包成 exe 后还需要系统装 Python？
因为 PyInstaller 本身需要在真实 Python 环境里工作（分析 AST、加载 hook、生成 spec）。PyPacker.exe 只是把 PyPacker 的界面冻结了，实际打包工作仍要调用系统的 python.exe。

解决方案：

目标机器装 Python + PyInstaller

或直接用源码运行 PyPacker（推荐）

🧰 技术栈
组件	用途
CustomTkinter	现代化 UI 控件
Pillow	图片处理、图标裁切
PyInstaller	核心打包引擎
Tkinter	GUI 底层框架
🤝 贡献
欢迎提 Issue 和 PR！

报告 bug：请附上打包日志和 %TEMP%\pypacker_icon_hook.log（如果涉及图标问题）

提交功能：请先开 Issue 讨论，避免重复劳动

代码风格：PEP 8，尽量保持模块职责单一

📄 许可
本项目基于 MIT License 开源，可自由用于商业和个人项目。

🙏 致谢
PyInstaller — 强大的 Python 打包工具

CustomTkinter — 让 Tkinter 也能很漂亮

Pillow — 图片处理的瑞士军刀

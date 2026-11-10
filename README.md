# Termius 简体中文补丁（非官方）

给 Termius **Windows 桌面版**做界面汉化的本地补丁。不改动业务逻辑、不触碰终端输出、
不联网、不上传任何数据，也不涉及登录凭据与加密数据。

> 本项目与 Termius Corporation 无关，仅供个人学习、本地使用。

## 汉化效果

词典 678 条，覆盖主界面与常用对话框。实际运行后已汉化的内容包括：

- 左侧栏：主机、钥匙串、端口转发、命令片段、已知主机、日志
- 工具栏：新建主机、终端、串口、连接
- 顶部标签：保险库、文件传输（SFTP）
- 原生菜单：文件、编辑、视图、窗口、帮助、检查更新、关于等
- 表单标签、按钮、状态提示、账户与团队、订阅等常见文案

少量动态拼接的长句、命令行补全描述、专有名词与用户自存数据保持英文。

## 原理

Termius 是 Electron 应用，界面文案编译在 `resources/app.asar` 内，官方没有中文语言包。
而且它启用了完整性校验：**exe 的 PE 资源里内嵌了 asar 头部的 SHA256，
asar 里每个文件还带独立的 SHA256 记录**。只改文案会导致程序拒绝启动。

补丁由三部分组成：

| 部分 | 说明 |
| --- | --- |
| 运行时翻译层 | `termius-zh.tpl.js` 生成 `termius-zh.js` 并注入两个页面 HTML；用词典匹配界面文本节点与 `placeholder` / `title` / `aria-label` 等属性，MutationObserver 处理 React 重渲染 |
| 精确静态替换 | 仅替换 `label:` / `title:` 等显示属性位置的字符串，覆盖原生菜单栏、窗口标题、表单标签 |
| 完整性重签 | 重算所有改动文件的 SHA256，并把 exe 内嵌的 64 位 hex 校验值原位更新（exe 其它字节不变） |

翻译层显式跳过 `.xterm-rows`、代码区、输入框与可编辑区域，**不会翻译远程主机在终端里输出的内容**。

## 文件说明

| 文件 | 用途 |
| --- | --- |
| `生成补丁.py` | 从原始 `app.asar` / `Termius.exe` 构建汉化版，可反复运行 |
| `termius-zh.tpl.js` | 运行时翻译层模板（词典占位符由构建脚本注入） |
| `词典.txt` / `词典.json` | 中英对照词典，每行 `English|简体中文` |
| `安装补丁.bat` / `还原补丁.bat` | 一键安装与回滚（自动备份原 asar） |
| `patch_exe.ps1` | 按固定偏移改写 exe 中 64 字节校验值，带前后校验 |
| `patch.example.json` | 构建产物示例，**仅对应特定版本**，不可跨版本套用 |

`app.asar`（约 177 MB）与 `Termius.exe` 不在仓库里，需按下面的步骤自行构建。

## 使用

### 方式一：已有构建好的补丁包

1. 完全退出 Termius（含托盘图标）。
2. 双击 `安装补丁.bat`：自动备份原 `app.asar` → 替换汉化版 → 修补 exe 校验值。
3. 还原：双击 `还原补丁.bat`。

### 方式二：从源码构建

1. 备份 Termius 安装目录，或确保安装目录同级存在完整的 `Termius.zip`
   （构建脚本用它提取**未经修改**的原始文件，保证可重复构建）。
2. 把本仓库文件放到任意目录，安装 Python 3。
3. 运行：

   ```bat
   set TERMIUS_DIR=%LOCALAPPDATA%\Programs\Termius
   python 生成补丁.py
   ```

   不设置 `TERMIUS_DIR` 时，脚本会自动探测 `%LOCALAPPDATA%\Programs\Termius`。
   产物在 `output\`：`app.asar`、`patch.json`、`词典.json`。
4. 退出 Termius，运行 `安装补丁.bat`。

备份位置：`Termius安装目录\_cn_patch\backup\app.asar.orig`。

## 重要提醒

- ⚠️ **版本绑定**：补丁针对特定 Termius 构建，`patch.json` 里的 exe 偏移与 hash 只对那一版有效。
  **换版本必须重新构建**，不要跨版本套用。
- ⚠️ **自动更新**：Termius 升级会替换 `app.asar` / `Termius.exe`。若 exe 里仍是补丁的校验值
  而 asar 已换成官方新版，校验不匹配会导致程序无法启动。**升级前先运行 `还原补丁.bat`**。
- **数字签名**：改写 exe 中 64 字节会使 Authenticode 签名失效，SmartScreen 可能提示
  "未知发布者"，选择"仍要运行"即可；还原后签名恢复。
- **汉化范围**：界面层汉化，不含命令行帮助、补全描述、专有名词和用户自存内容。

## 扩充词典

编辑 `词典.txt`，每行一条 `英文原文|简体中文`；`#` 开头是注释，
英文末尾**留一个空格**表示组合短语前缀（如 `Continue with |继续使用` 可匹配
"Continue with Google"）。改完重新运行 `生成补丁.py` 并重新安装即可。

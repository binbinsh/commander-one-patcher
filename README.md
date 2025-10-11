# Commander One 中文汉化优化项目

## 简介

本项目旨在优化 macOS 双栏文件管理器 [Commander One](https://commander-one.com/) 的官方简体中文（zh-Hans）翻译，使其更符合中文用户的使用习惯，并修正一些官方翻译中存在的不够地道或有歧义的地方。

本仓库通过 Git 标签（Tag）来管理与 Commander One 主程序版本对应的翻译文件。

## ✨ 特点

-   **更地道**：使用更符合中文语境的词汇。
-   **更精准**：修正原文理解错误或生硬的机器翻译。
-   **同步更新**：随着 Commander One 的版本更新而持续维护。

## 🚀 如何使用

本项目提供了一个自动化脚本，可以一键将优化后的汉化包应用到您的 Commander One 中。

**第一步：克隆本仓库到本地**

```bash
git clone git@github.com:binbinsh/commander-one-zh-hans.git
```

**第二步：运行更新脚本**

进入仓库目录，然后执行脚本。脚本会自动检测您当前安装的 Commander One 版本，并应用对应的汉化包。

```bash
cd commander-one-zh-hans
bash update-translation.sh
```

> **注意**：脚本会自动备份官方原版语言文件，可随时恢复。

操作完成后，**重启 Commander One** 即可看到效果。

## ⚠️ 重要提示

修改 `.app` 应用包内的任何文件都会**破坏其原始的代码签名**。虽然这通常不会影响 Commander One 的正常运行，但请知悉此情况。

## 许可协议

本项目采用 [MIT](https://opensource.org/licenses/MIT) 许可协议。

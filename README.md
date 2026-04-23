# Commander One Patcher

## 简介

这个仓库现在用于维护两类独立的 **Commander One 修复脚本**。

补丁针对我本机当前分析过的版本：

- `Commander One 3.17.1`
- `CFBundleVersion 3990`
- `arm64` slice SHA-256:
  `17c3b6060e28333568606103a19dbea3940cea00ab903e137ee6d5acd28fa064`

目标有两类，而且现在已经拆成独立入口：

- 阻止 `Commander One` 再次把左右面板状态写回 `SavedLeftTabs` / `SavedRightTabs`
- 把当前用户偏好里的左右面板启动页规范化为本地页
- 同时应用仓库里的 `zh-Hans.lproj` 中文翻译

## 方案

## 入口

- `patch-commander-one.py`
  只做二进制补丁、重签名、可选 prefs 规范化
- `update-translation.sh`
  只做 `zh-Hans.lproj` 资源更新和重签名
## 二进制补丁

`patch-commander-one.py` 会做下面几件事：

1. 默认直接针对 `/Applications/Commander One.app` 工作。
2. 先整包备份原始 app。
3. 在临时副本里补丁 `arm64` 主二进制。
4. 对结果重新做 ad-hoc 签名。
5. 最后再把处理好的 app 写回目标路径。

二进制补丁只禁用两类调用点：
   - 退出时回写 `SavedLeftTabs`
   - 退出时回写 `SavedRightTabs`

启动恢复路径保留原样，避免破坏 Commander One 自己的初始化假设。第一次应用补丁时，通过用户偏好规范化把左右启动页切回本地目录，从而规避慢启动。

这样做的结果是：

- 保留 `Commander One` 的 `SFTP` 插件本体，不像移除 `TCXFtpFS.bundle` 那样直接失去功能。
- 不再恢复上次左右面板标签页状态。
- 因为不再恢复远程页，冷启动不会被远程连接探测拖慢。

## 使用

只打补丁：

```bash
cd ~/Projects/Personal/commander-one-patcher
./patch-commander-one.py
```

只更新翻译：

```bash
./update-translation.sh
```

如果想给 `patch-commander-one.py` 显式指定备份路径：

```bash
./patch-commander-one.py \
  --backup-app "/Applications/Commander One.app.backup-manual"
```

如果想顺手把当前用户偏好里的旧慢启动状态一起规范化为本地页：

```bash
./patch-commander-one.py --sanitize-prefs --clear-saved-state
```

## 限制

- 当前补丁 **只支持上面列出的 3.17.1 / 3990 / arm64 hash**。
- `x86_64` slice 只会被保留，不会被补丁；在 Apple Silicon 正常原生启动时这不影响使用。
- 这是**版本绑定**补丁。Commander One 更新后，偏移和字节校验大概率都会变，需要重新分析。
- `patch-commander-one.py` 默认是原地替换 `/Applications/Commander One.app`，但会先做整包备份。
- `update-translation.sh` 默认只备份当前 `zh-Hans.lproj`。

## 风险

- 两个脚本都会修改 `.app` 包内容，并重新签名结果 app。
- 这是本地二进制补丁，不是官方支持方式。
- 补丁后的行为是“左右面板状态不再自动持久化回用户偏好”，这是有意 tradeoff。
- 默认行为会替换 `/Applications/Commander One.app`，所以脚本在 app 运行时会直接拒绝执行。

## 仓库说明

当前主要入口是：

- `patch-commander-one.py`
- `update-translation.sh`

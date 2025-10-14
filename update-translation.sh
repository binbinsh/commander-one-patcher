#!/bin/bash

# --- 动态配置区 ---
# 自动获取脚本所在目录的绝对路径，这也就是 Git 仓库的根目录。
REPO_PATH=$(cd "$(dirname "$0")" && pwd)
# --- 静态配置区 ---
# Commander One 的安装路径
APP_PATH="/Applications/Commander One.app"
# --- 配置区结束 ---


# 设置颜色，让输出更友好
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # 无颜色

# 脚本出错时立即退出
set -e

printf "${GREEN}### Commander One 汉化更新脚本 v2.1 ###${NC}\n"

# 1. 检查 Commander One 是否已安装
if [ ! -d "$APP_PATH" ]; then
    printf "${RED}错误：未在路径 $APP_PATH 找到 Commander One.app。${NC}\n"
    exit 1
fi
echo "✅ 已找到 Commander One 应用。"

# 2. 获取当前安装的 Commander One 版本号
INSTALLED_VERSION=$(defaults read "$APP_PATH/Contents/Info.plist" CFBundleShortVersionString)
if [ -z "$INSTALLED_VERSION" ]; then
    printf "${RED}错误：无法读取 Commander One 的版本号。${NC}\n"
    exit 1
fi
# 使用 printf 进行格式化输出，确保颜色正常
printf "🔍 当前应用版本为 ${YELLOW}%s${NC}，需要匹配 Git 标签 ${YELLOW}%s${NC}。\n" "$INSTALLED_VERSION" "v$INSTALLED_VERSION"
GIT_TAG="v$INSTALLED_VERSION"

# 3. 前往 Git 仓库目录
cd "$REPO_PATH"
echo "🔄 正在进入仓库目录: $REPO_PATH"
# Try to refresh tags from remote (ignore failures to keep script robust)
git fetch --tags --quiet > /dev/null 2>&1 || true

# 4. 检查对应的 Git 标签是否存在；若无精确匹配，寻找“最接近”的标签
if ! git tag --list | grep -q "^$GIT_TAG$"; then
    # Fallback to closest within the same major.minor (e.g., 1.7.1 -> v1.7*)
    MAJOR=$(echo "$INSTALLED_VERSION" | cut -d. -f1)
    MINOR=$(echo "$INSTALLED_VERSION" | cut -d. -f2)
    if [ -n "$MINOR" ]; then
        BASE="${MAJOR}.${MINOR}"
    else
        BASE="${MAJOR}"
    fi

    # Candidates: v<BASE> or v<BASE>.<patch...>
    CANDIDATES=$(git tag --list | grep -E "^v${BASE//./\\.}(\\.|$)" || true)

    if [ -n "$CANDIDATES" ]; then
        BEST_VERSION=$(echo "$CANDIDATES" | sed 's/^v//' | sort -V | tail -n 1)
        GIT_TAG="v$BEST_VERSION"
        printf "${YELLOW}⚠️ 未找到精确标签 v%s，使用最接近的标签 %s。${NC}\n" "$INSTALLED_VERSION" "$GIT_TAG"
    else
        printf "${RED}错误：在本地 Git 仓库中未找到标签 ${GIT_TAG}，也未找到同一主次版本的标签。${NC}\n"
        printf "${YELLOW}请确保您已经为版本 ${INSTALLED_VERSION} 创建了对应的汉化并打了标签。${NC}\n"
        exit 1
    fi
fi
echo "✅ 已在 Git 仓库中找到标签 ${GIT_TAG}。"

# 5. 检出对应的标签版本
echo "📦 正在检出版本 ${GIT_TAG} 的翻译文件..."
# 使用 stash 来保存任何未提交的更改，确保可以干净地切换
git stash push -m "Auto-stash before update" > /dev/null 2>&1
git checkout "$GIT_TAG"

# 6. 执行更新操作
TARGET_LPROJ_PATH="$APP_PATH/Contents/Resources/zh-Hans.lproj"
SOURCE_LPROJ_PATH="$REPO_PATH/zh-Hans.lproj"
BACKUP_PATH="$APP_PATH/Contents/Resources/zh-Hans.lproj.backup_$(date +%Y%m%d_%H%M%S)"

printf "🛡️ 正在备份原始语言文件到 ${YELLOW}%s${NC}...\n" "$BACKUP_PATH"
# 使用 sudo 是因为 /Applications 目录需要管理员权限
if [ -d "$TARGET_LPROJ_PATH" ]; then
    sudo mv "$TARGET_LPROJ_PATH" "$BACKUP_PATH"
else
    printf "${YELLOW}警告：原始语言文件不存在，无需备份。${NC}\n"
fi

echo "🚀 正在应用新的汉化文件..."
sudo cp -R "$SOURCE_LPROJ_PATH" "$APP_PATH/Contents/Resources/"

# 7. 返回到主分支并恢复之前的状态
git checkout main
git stash pop > /dev/null 2>&1 || true # 如果没有 stash 内容，pop 会失败，|| true 避免脚本因此退出

printf "\n${GREEN}🎉 成功！Commander One 的简体中文语言包已更新至版本 ${INSTALLED_VERSION}。${NC}\n"
printf "${YELLOW}请重启 Commander One 以应用更改。${NC}\n"

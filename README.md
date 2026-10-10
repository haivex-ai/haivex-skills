# Haivex Skills

Haivex 官方文件技能。正文、脚本和模板以本仓库为唯一发布来源，客户端从 `haivex-ai/haivex-skills` 的 `main` 分支安装到本机。目录采用 Codex 官方的 marketplace 与纯技能插件格式。

## 目录

```text
.agents/plugins/marketplace.json
plugins/
  skill-creator/
    plugin.json
    skills/skill-creator/
      SKILL.md
      agents/openai.yaml
      scripts/
  dsz-product-delivery/
    plugin.json
    skills/dsz-product-delivery/
      SKILL.md
      agents/openai.yaml
      templates/
```

`marketplace.json` 决定展示哪些插件，`source.path` 相对于仓库根目录；其中 `source: local` 表示包在同一仓库内，不是用户电脑上的路径。`plugin.json` 使用官方当前推荐的 portable 插件格式，声明名称和版本，技能自动从包内 `skills/` 发现。技能本身仍遵循 `SKILL.md` 与可选 `agents/openai.yaml` 格式。

这里只发布纯技能插件，GitHub 仓库就是分发来源，不需要 `package.json` 或 `npm publish`。Codex 也支持 npm 来源，但这不是技能文件格式的要求。

参考：[官方插件打包说明](https://developers.openai.com/plugins/build/plugins) · [官方插件示例仓库](https://github.com/openai/plugins)。

## 首次发布

创建公开 GitHub 仓库 `haivex-ai/haivex-skills`，默认分支使用 `main`，提交本目录全部文件。若使用 GitHub CLI，可在本目录执行：

```sh
git init -b main
git add .
git commit -m "Add initial Haivex skills"
gh repo create haivex-ai/haivex-skills --public --source=. --remote=origin --push
```

如果已在网页创建空仓库，将最后一行改为：

```sh
git remote add origin https://github.com/haivex-ai/haivex-skills.git
git push -u origin main
```

不需要上传 R2、登记数据库、运行构建或部署后台。客户端需要更新到支持 GitHub 技能来源的版本。

## 日常修改

1. 修改目标技能的 `SKILL.md`、`agents/openai.yaml` 或资源文件。
2. 将对应 `plugins/<插件名>/plugin.json` 中的 `version` 递增，例如 `1.0.0` → `1.0.1`。
3. 将文件和版本号一起提交并推送到 `main`。
4. 客户端刷新技能页后即可安装或更新。

名称或文件修改后也要递增对应版本。恢复历史内容时同样提高版本号，客户端不会降级；本地有修改时不会被官方更新覆盖。从 marketplace 移除条目相当于下架，不会删除用户已安装的文件。

新增独立插件时创建 `plugins/<插件名>/plugin.json`，在其 `skills/<id>/` 中补完 `SKILL.md` 和资源，再在 marketplace 添加来源条目。一个插件可以带多个技能，包内技能共用插件版本。模板等资源直接提交到 Git，不使用需要额外下载的 Git LFS 指针文件。

## 验证

创建器脚本不依赖额外安装的包，使用 Bun：

```sh
bun test tests
bun plugins/skill-creator/skills/skill-creator/scripts/quick_validate.ts plugins/skill-creator/skills/skill-creator
bun plugins/skill-creator/skills/skill-creator/scripts/quick_validate.ts plugins/dsz-product-delivery/skills/dsz-product-delivery
```

客户端安装时固定一个 Git 提交，目录与资源始终取自同一提交；安装后任务使用本地文件。创建器沿用其正文中的来源说明。

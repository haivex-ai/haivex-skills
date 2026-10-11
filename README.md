# Haivex Skills

Haivex 官方技能源码。技能沿用 Codex 的 marketplace 与 portable plugin 格式，**通过 GitHub Release 版本包分发**。修改或推送源码不会直接更新用户安装的技能，执行发布命令后才生效。

## 发布或更新

首次准备：安装 Bun 和 GitHub CLI，运行 `gh auth login` 登录有仓库写入权限的账号，然后在本目录运行一次 `bun install`。

修改 `plugins/dsz-product-delivery/skills/dsz-product-delivery/SKILL.md` 或其中的模板后：

```sh
bun run publish dsz-product-delivery
```

创建器同理：

```sh
bun run publish skill-creator
```

命令自动完成：

1. 检查技能内容、市场条目、当前分支及远端状态。
2. 将目标插件的 `plugin.json` 版本自动增加一个 patch，例如 `1.0.0` → `1.0.1`。
3. 只提交目标插件目录与 marketplace，推送 `main`。
4. 从该 Git 提交生成包含技能正文、配置、脚本和模板的 ZIP 包。
5. 创建 Release 草稿，上传并核对 SHA-256 与大小，全部成功后正式发布。

客户端刷新技能页后可检测到新版并点击「更新」。技能更新不需要重新发客户端，不使用 R2、数据库或 npm registry，也不要求下载者登录 GitHub。发布命令中的 `package.json` 仅管理开发脚本与打包依赖。

发布前暂存区需为空，本地 `main` 不能落后于远端；命令不会自动合并分支。其他插件的未提交修改不会被加入本次提交。

如果 GitHub CLI 直连超时，需通过 `HTTPS_PROXY` 环境变量传入本机代理地址；`gh` 不一定自动读取操作系统的代理设置。发布命令继承终端环境，不保存代理或账号凭据。

## 预览与重试

仅生成本地包，不增加版本、不提交、不上传：

```sh
bun run pack dsz-product-delivery
```

产物在忽略提交的 `dist/` 中。预览包允许包含未提交的编辑；正式包始终从固定的 Git 提交生成。

首次发布已有版本，或发布失败后继续相同版本：

```sh
bun run publish dsz-product-delivery --no-bump
```

发布失败后已增加的版本不会回退。`--no-bump` 会复用同版本草稿并核对已有附件；相同版本已成功发布时直接返回，禁止覆盖不同内容。若命令被强制终止留下 `.git/haivex-skill-publish.lock`，确认没有发布任务运行后再删除该锁文件。

## 包格式与版本

```text
.agents/plugins/marketplace.json
plugins/<插件名>/
  plugin.json
  skills/<技能名>/
    SKILL.md
    agents/openai.yaml
    scripts/ 或 templates/
```

marketplace 的 `source.path` 相对于仓库根目录；`source: local` 表示同仓库内的插件。一个插件可以带多个技能，包内技能共用插件版本。包不包含其他插件或仓库开发脚本。

每个插件独立创建 Release，例如 `dsz-product-delivery@1.0.1`，附件为 `dsz-product-delivery-1.0.1.zip`。客户端只读取正式发布、非预发布的 Release，按每个插件的版本号选择最新包；从包内原始文件读取显示名称与描述，验证下载摘要、大小、路径及版本。

恢复旧内容时以更高版本重新发布。客户端不降级，本地有修改的技能不会被覆盖。需要下架整个插件时，将它的正式 Releases 全部改为草稿或删除；只撤回最新版本会重新展示前一个正式版本，已安装的更高版本仍不会降级。仅改 main 的 marketplace 不改变已发布包。

当前 Haivex 只支持纯技能插件，不是完整的 Codex 插件运行时。包结构兼容现有 Codex 格式；Release 发布与更新是 Haivex 的分发流程。参考：[官方插件打包说明](https://developers.openai.com/plugins/build/plugins)。

## 验证

```sh
bun test tests
```

创建器脚本与包内技能文件保持独立，不依赖本仓库开发环境。运行中使用的安装目录为 `~/.multi-agents/skills/`。

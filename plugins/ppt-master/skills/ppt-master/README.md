# PPT Master 演示文稿

用于创建、重构、美化和编辑可编辑的 PowerPoint 演示文稿，也支持品牌/样式/版式/整套模板、旁白与动画。

## 使用方式

向 Agent 提供主题、素材、目标受众、页数和交付要求，或提交需要重构、美化、修改的已有 PPTX、图片和模板。Agent 读取 `SKILL.md`，运行归属完整性检查，再按所选工作流执行。

交付取决于所选工作流，可包含可编辑 PPTX、预览图、模板工作区、讲稿或配音与播放产物。各工作流的用户确认步骤以包内规则为准。

## 运行条件

- 需要 Python；按实际使用的功能安装 `requirements.txt` 中的依赖，不随技能复制本机虚拟环境。
- 部分功能需要 LibreOffice、FFmpeg 或工作流声明的其他外部工具；图像和语音服务可能需要单独配置提供方与授权。
- `.env.example` 是配置示例，不包含本机授权；个人配置与凭据不随技能发布。
- 运行时以宿主提供的技能绝对目录为准；不依赖某台电脑的 Downloads 目录或虚拟环境路径。

## 来源与许可

作者：Hugo He。上游版本：6.8.0。

上游项目：https://github.com/hugohe3/ppt-master

项目许可见 [LICENSE](LICENSE)。原作者的归属信息、完整性检查与赞助说明完整保留。图标、声音等第三方资源遵循各自的许可及声明，见 `templates/icons/THIRD_PARTY_NOTICES.md`、`templates/sounds/THIRD_PARTY_NOTICES.md` 和资源目录内的说明。

本副本仅增加 Haivex 中文展示元数据和此用户概览，工作流、脚本及静态资产沿用本地已安装的 6.8.0 版本。

# Codex PPT Skills

目前收录 [classroom-ppt](.agents/skills/classroom-ppt/SKILL.md)，用于制作和修订中文课程汇报 PPT。包含故事式讲述、真实素材与论文引用、原生动画和内嵌视频的放映验收。

在本仓库中打开 Codex 后，可用 `$classroom-ppt` 调用。要在其他项目中使用，可把 `.agents/skills/classroom-ppt` 整个目录复制到目标项目的 `.agents/skills/` 下。

遇到动画消失时，可以对照两份文件运行：

```shell
python .agents/skills/classroom-ppt/scripts/check_playback.py 原始版.pptx 用户打开的副本.pptx
```

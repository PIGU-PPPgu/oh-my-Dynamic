# 视频展示

`showcase/` 里的 Remotion 项目把 v3.5 的身份、证据和官方诉求做成一段
对外展示视频。

## 展示内容

- 问题：Codex App 目前缺少公开的 App-native dynamic workflow fan-out runtime。
- 证明：Codex CLI process swarm、planner/replanner、broker evidence、strict
  doctor、safe CI examples。
- 边界：oh-my-Dynamic 不声称已经实现 Codex App-native isolated subagents。
- 诉求：native subagent API、sandbox/scheduler/tool-permission contracts、
  event streams、artifact ownership interfaces。

## 命令

```bash
cd showcase
npm install
npm run typecheck
npm run still
npm run poster
npm run render
```

渲染结果会写入 `showcase/out/`，默认不提交。

README 使用 GitHub `user-attachments` MP4 URL，因为 GitHub 会过滤普通仓库
README 里的相对路径 `<video>` 标签。提交到仓库的 MP4 仍可作为备用链接：
`assets/oh-my-dynamic-showcase.mp4`。

## 推荐用途

- 把 MP4 附到 GitHub Release notes。
- 把 still 用作社媒预览图或 discussion 缩略图。
- 和 [OFFICIAL_BRIEF.zh-CN.md](OFFICIAL_BRIEF.zh-CN.md)、
  [OUTREACH.zh-CN.md](OUTREACH.zh-CN.md) 一起发给外部 reviewer。

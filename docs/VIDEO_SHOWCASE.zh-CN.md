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

## 推荐用途

- 把 MP4 附到 GitHub Release notes。
- 把 still 用作社媒预览图或 discussion 缩略图。
- 和 [OFFICIAL_BRIEF.zh-CN.md](OFFICIAL_BRIEF.zh-CN.md)、
  [OUTREACH.zh-CN.md](OUTREACH.zh-CN.md) 一起发给外部 reviewer。

# oh-my-Dynamic Remotion Showcase

This folder contains a short official-facing showcase video for
oh-my-Dynamic. It is intentionally separate from the Python runtime and does
not change workflow behavior.

## Render

```bash
cd showcase
npm install
npm run typecheck
npm run still
npm run poster
npm run render
```

Outputs are written to `showcase/out/` and are ignored by git.

## Compositions

- `OhMyDynamicShowcase`: 75-second 1920x1080 video.
- `OhMyDynamicPoster`: 1200x630 still for social previews.

## Message

The video is safe for external review because it says:

- verified large-scale execution is Codex CLI process swarm;
- the project does not claim App-native isolated subagents are implemented;
- public runtime contracts are the ask: subagent API, sandbox, scheduler,
  tool permissions, events, and artifacts.

No OpenAI, Codex, or ChatGPT official marks are used.

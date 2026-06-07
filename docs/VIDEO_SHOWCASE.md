# Video Showcase

The Remotion showcase in `showcase/` turns the v3.5 identity material into a
short external-facing video.

## What It Shows

- The problem: Codex App lacks a public App-native dynamic workflow fan-out
  runtime.
- The proof: Codex CLI process swarm, planner/replanner loops, broker evidence,
  strict doctor checks, and safe CI examples.
- The boundary: oh-my-Dynamic does not claim App-native isolated subagents are
  implemented.
- The ask: native subagent API, sandbox/scheduler/tool-permission contracts,
  event streams, and artifact ownership interfaces.

## Commands

```bash
cd showcase
npm install
npm run typecheck
npm run still
npm run poster
npm run render
```

Rendered files go to `showcase/out/` and are not committed by default.

## Recommended Use

- Attach the MP4 to the GitHub Release notes.
- Use the still as a social preview or discussion thumbnail.
- Pair the video with [OFFICIAL_BRIEF.md](OFFICIAL_BRIEF.md) and
  [OUTREACH.md](OUTREACH.md).

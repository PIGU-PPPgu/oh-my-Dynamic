import React from 'react';
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

const palette = {
  ink: '#0b1117',
  ink2: '#111c25',
  paper: '#f4f8fb',
  muted: '#a7b4bf',
  line: '#2a3a47',
  teal: '#37c7b7',
  blue: '#5da9ff',
  amber: '#f2b84b',
  green: '#7bd66f',
  red: '#ff7171',
};

const ease = Easing.bezier(0.16, 1, 0.3, 1);

const fade = (frame: number, start: number, duration: number) =>
  interpolate(frame, [start, start + duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: ease,
  });

const rise = (frame: number, start: number, duration: number) =>
  interpolate(frame, [start, start + duration], [28, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: ease,
  });

type SceneProps = {
  children: React.ReactNode;
};

const Scene: React.FC<SceneProps> = ({children}) => (
  <AbsoluteFill
    style={{
      background:
        'radial-gradient(circle at 72% 18%, rgba(55, 199, 183, 0.16), transparent 28%), linear-gradient(135deg, #0b1117 0%, #101821 56%, #162533 100%)',
      color: palette.paper,
      fontFamily:
        'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      overflow: 'hidden',
    }}
  >
    <Grid />
    <div style={{position: 'relative', width: '100%', height: '100%'}}>
      {children}
    </div>
  </AbsoluteFill>
);

const Grid: React.FC = () => (
  <div
    style={{
      position: 'absolute',
      inset: 0,
      backgroundImage:
        'linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px)',
      backgroundSize: '56px 56px',
      maskImage:
        'linear-gradient(to bottom, rgba(0,0,0,0.8), rgba(0,0,0,0.2))',
    }}
  />
);

type TextBlockProps = {
  eyebrow?: string;
  title: string;
  body?: string;
  frame: number;
  start: number;
  width?: number;
  left?: number;
  top?: number;
};

const TextBlock: React.FC<TextBlockProps> = ({
  eyebrow,
  title,
  body,
  frame,
  start,
  width = 980,
  left = 110,
  top = 132,
}) => {
  const opacity = fade(frame, start, 22);
  const translateY = rise(frame, start, 22);

  return (
    <div
      style={{
        position: 'absolute',
        left,
        top,
        width,
        opacity,
        transform: `translateY(${translateY}px)`,
      }}
    >
      {eyebrow ? (
        <div
          style={{
            color: palette.teal,
            fontSize: 28,
            fontWeight: 700,
            letterSpacing: 0,
            marginBottom: 24,
            textTransform: 'uppercase',
          }}
        >
          {eyebrow}
        </div>
      ) : null}
      <div
        style={{
          fontSize: 86,
          lineHeight: 0.98,
          fontWeight: 820,
          letterSpacing: 0,
        }}
      >
        {title}
      </div>
      {body ? (
        <div
          style={{
            marginTop: 32,
            color: palette.muted,
            fontSize: 32,
            lineHeight: 1.35,
            maxWidth: 900,
          }}
        >
          {body}
        </div>
      ) : null}
    </div>
  );
};

type PillProps = {
  text: string;
  color?: string;
};

const Pill: React.FC<PillProps> = ({text, color = palette.blue}) => (
  <div
    style={{
      border: `1px solid ${color}`,
      background: `${color}18`,
      color: palette.paper,
      borderRadius: 8,
      padding: '12px 18px',
      fontSize: 24,
      fontWeight: 700,
      whiteSpace: 'nowrap',
    }}
  >
    {text}
  </div>
);

const Node: React.FC<{
  x: number;
  y: number;
  label: string;
  color?: string;
  frame: number;
  start: number;
}> = ({x, y, label, color = palette.blue, frame, start}) => {
  const opacity = fade(frame, start, 18);
  const scale = interpolate(frame, [start, start + 18], [0.84, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: ease,
  });
  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        width: 210,
        height: 76,
        opacity,
        transform: `scale(${scale})`,
        border: `2px solid ${color}`,
        background: '#111b24e6',
        borderRadius: 8,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: palette.paper,
        fontWeight: 760,
        fontSize: 23,
        boxShadow: `0 0 34px ${color}35`,
      }}
    >
      {label}
    </div>
  );
};

const Line: React.FC<{
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  frame: number;
  start: number;
  color?: string;
}> = ({x1, y1, x2, y2, frame, start, color = palette.line}) => {
  const progress = fade(frame, start, 24);
  return (
    <svg
      width={1920}
      height={1080}
      style={{position: 'absolute', inset: 0, overflow: 'visible'}}
    >
      <line
        x1={x1}
        y1={y1}
        x2={x1 + (x2 - x1) * progress}
        y2={y1 + (y2 - y1) * progress}
        stroke={color}
        strokeWidth={4}
        strokeLinecap="round"
      />
    </svg>
  );
};

const GraphScene: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <>
    <TextBlock
      eyebrow="Problem"
      title="Codex needs dynamic workflow fan-out."
      body="oh-my-Dynamic demonstrates the contract with process swarms, planner/replanner loops, and reviewable broker evidence."
      frame={frame}
      start={8}
    />
    <>
      <Line x1={1460} y1={320} x2={1250} y2={450} frame={frame} start={40} color={palette.teal} />
      <Line x1={1460} y1={320} x2={1460} y2={450} frame={frame} start={45} color={palette.teal} />
      <Line x1={1460} y1={320} x2={1670} y2={450} frame={frame} start={50} color={palette.teal} />
      <Line x1={1250} y1={490} x2={1460} y2={650} frame={frame} start={72} color={palette.amber} />
      <Line x1={1460} y1={490} x2={1460} y2={650} frame={frame} start={76} color={palette.amber} />
      <Line x1={1670} y1={490} x2={1460} y2={650} frame={frame} start={80} color={palette.amber} />
      <Node x={1355} y={282} label="planner" color={palette.teal} frame={frame} start={26} />
      <Node x={1145} y={430} label="agent 01" frame={frame} start={46} />
      <Node x={1355} y={430} label="agent 02" frame={frame} start={52} />
      <Node x={1565} y={430} label="agent N" frame={frame} start={58} />
      <Node x={1355} y={640} label="reducer" color={palette.amber} frame={frame} start={86} />
    </>
    </>
  );
};

const ArchitectureScene: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <>
    <TextBlock
      eyebrow="Architecture"
      title="Planner. Swarm. Evidence. Replanner."
      body="The verified large-scale path is Codex CLI process swarm, not an App-native isolated subagent claim."
      frame={frame}
      start={0}
      width={1080}
    />
    <div
      style={{
        position: 'absolute',
        left: 100,
        bottom: 116,
        display: 'flex',
        gap: 22,
        opacity: fade(frame, 40, 20),
      }}
    >
      <Pill text="read-only default" color={palette.green} />
      <Pill text="worktree mode explicit" color={palette.amber} />
      <Pill text="raw traces stay local" color={palette.blue} />
    </div>
    <div
      style={{
        position: 'absolute',
        right: 90,
        top: 210,
        width: 620,
        display: 'grid',
        gridTemplateColumns: '1fr',
        gap: 22,
      }}
    >
      {[
        ['1', 'Planner creates review agents'],
        ['2', 'Codex CLI workers run in parallel'],
        ['3', 'Broker records events and artifacts'],
        ['4', 'Replanner fills gaps and failures'],
        ['5', 'Reducer produces compact evidence'],
      ].map(([n, text], index) => (
        <div
          key={n}
          style={{
            opacity: fade(frame, 22 + index * 12, 18),
            transform: `translateX(${interpolate(
              frame,
              [22 + index * 12, 42 + index * 12],
              [30, 0],
              {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease},
            )}px)`,
            border: `1px solid ${palette.line}`,
            background: '#101923e6',
            borderRadius: 8,
            padding: '24px 28px',
            display: 'flex',
            alignItems: 'center',
            gap: 22,
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 8,
              background: palette.teal,
              color: palette.ink,
              fontSize: 24,
              fontWeight: 900,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {n}
          </div>
          <div style={{fontSize: 28, fontWeight: 720}}>{text}</div>
        </div>
      ))}
    </div>
    </>
  );
};

const EvidenceScene: React.FC = () => {
  const frame = useCurrentFrame();
  const cards = [
    ['100', 'real fixed-swarm agents recorded', palette.blue],
    ['82%', 'pytest coverage gate passed', palette.green],
    ['5/20/50/100', 'compact evidence sizes', palette.teal],
    ['strict', 'doctor + safe CI examples', palette.amber],
  ];
  return (
    <>
      <TextBlock
        eyebrow="Evidence"
        title="Claims are paired with compact, sanitized records."
        body="Evidence separates controlled rubric lift from real Codex CLI smoke, and preserves failures instead of hiding them."
        frame={frame}
        start={0}
      />
      <div
        style={{
          position: 'absolute',
          left: 110,
          bottom: 120,
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 22,
          width: 1700,
        }}
      >
        {cards.map(([value, label, color], index) => (
          <div
            key={value}
            style={{
              opacity: fade(frame, 44 + index * 10, 18),
              transform: `translateY(${rise(frame, 44 + index * 10, 18)}px)`,
              background: '#101923e6',
              border: `1px solid ${color}`,
              borderRadius: 8,
              padding: 30,
              minHeight: 190,
            }}
          >
            <div style={{fontSize: 58, fontWeight: 900, color}}>{value}</div>
            <div style={{marginTop: 18, fontSize: 25, lineHeight: 1.25, color: palette.muted}}>
              {label}
            </div>
          </div>
        ))}
      </div>
    </>
  );
};

const AskScene: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <>
    <TextBlock
      eyebrow="Runtime ask"
      title="Make dynamic workflows native."
      body="The project asks for public contracts: subagent spawning, sandbox isolation, scheduler controls, tool permissions, and event/artifact interfaces."
      frame={frame}
      start={0}
      width={1120}
    />
    <div
      style={{
        position: 'absolute',
        right: 130,
        top: 190,
        width: 560,
        padding: 34,
        borderRadius: 8,
        border: `1px solid ${palette.red}`,
        background: '#151d24f2',
        opacity: fade(frame, 38, 20),
      }}
    >
      <div style={{color: palette.red, fontSize: 26, fontWeight: 900, marginBottom: 18}}>
        Explicit non-claim
      </div>
      <div style={{fontSize: 35, lineHeight: 1.18, fontWeight: 760}}>
        does not claim App-native isolated subagents are implemented
      </div>
    </div>
    <div
      style={{
        position: 'absolute',
        left: 110,
        bottom: 110,
        display: 'flex',
        gap: 20,
        opacity: fade(frame, 58, 20),
      }}
    >
      <Pill text="native subagent API" />
      <Pill text="sandbox contracts" />
      <Pill text="event streams" />
      <Pill text="artifact ownership" />
    </div>
    </>
  );
};

const ClosingScene: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <>
    <div
      style={{
        position: 'absolute',
        left: 116,
        top: 120,
        display: 'flex',
        alignItems: 'center',
        gap: 26,
        opacity: fade(frame, 0, 20),
      }}
    >
      <Img src={staticFile('icon.svg')} style={{width: 96, height: 96}} />
      <div>
        <div style={{fontSize: 60, fontWeight: 900}}>oh-my-Dynamic</div>
        <div style={{fontSize: 28, color: palette.muted, marginTop: 8}}>
          Dynamic workflow tooling for Codex
        </div>
      </div>
    </div>
    <TextBlock
      title="A reproducible prototype for the runtime we want."
      body="Brief, demo script, outreach pack, and sanitized evidence are ready for external review."
      frame={frame}
      start={28}
      width={1180}
      top={342}
    />
    <div
      style={{
        position: 'absolute',
        left: 116,
        bottom: 118,
        fontSize: 32,
        color: palette.teal,
        opacity: fade(frame, 70, 20),
        fontWeight: 800,
      }}
    >
      github.com/PIGU-PPPgu/oh-my-Dynamic
    </div>
    </>
  );
};

export const ShowcaseVideo: React.FC = () => {
  return (
    <AbsoluteFill>
      <Sequence from={0} durationInFrames={420}>
        <Scene>
          <GraphScene />
        </Scene>
      </Sequence>
      <Sequence from={420} durationInFrames={480}>
        <Scene>
          <ArchitectureScene />
        </Scene>
      </Sequence>
      <Sequence from={900} durationInFrames={450}>
        <Scene>
          <EvidenceScene />
        </Scene>
      </Sequence>
      <Sequence from={1350} durationInFrames={450}>
        <Scene>
          <AskScene />
        </Scene>
      </Sequence>
      <Sequence from={1800} durationInFrames={450}>
        <Scene>
          <ClosingScene />
        </Scene>
      </Sequence>
    </AbsoluteFill>
  );
};

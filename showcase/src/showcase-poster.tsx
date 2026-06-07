import React from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';

export const ShowcasePoster: React.FC = () => (
  <AbsoluteFill
    style={{
      background:
        'radial-gradient(circle at 76% 16%, rgba(55, 199, 183, 0.18), transparent 30%), linear-gradient(135deg, #0b1117 0%, #101821 58%, #162533 100%)',
      color: '#f4f8fb',
      fontFamily:
        'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      padding: 72,
    }}
  >
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 24,
        marginBottom: 56,
      }}
    >
      <Img src={staticFile('icon.svg')} style={{width: 82, height: 82}} />
      <div>
        <div style={{fontSize: 54, fontWeight: 900}}>oh-my-Dynamic</div>
        <div style={{fontSize: 24, color: '#a7b4bf', marginTop: 6}}>
          Dynamic workflow tooling for Codex
        </div>
      </div>
    </div>
    <div style={{fontSize: 72, fontWeight: 900, lineHeight: 0.98, width: 860}}>
      Planner/replanner swarms with broker evidence.
    </div>
    <div style={{marginTop: 34, fontSize: 28, color: '#a7b4bf', width: 820, lineHeight: 1.35}}>
      A reproducible prototype for Codex dynamic workflow runtime contracts,
      without claiming App-native isolated subagents are implemented.
    </div>
    <div
      style={{
        position: 'absolute',
        right: 72,
        top: 408,
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        alignItems: 'stretch',
      }}
    >
      {['100-agent evidence', 'strict doctor', 'safe CI examples'].map((item) => (
        <div
          key={item}
          style={{
            border: '1px solid #37c7b7',
            background: '#37c7b718',
            borderRadius: 8,
            padding: '12px 16px',
            fontSize: 20,
            fontWeight: 760,
            textAlign: 'center',
          }}
        >
          {item}
        </div>
      ))}
    </div>
  </AbsoluteFill>
);

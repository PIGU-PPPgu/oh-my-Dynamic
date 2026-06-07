import React from 'react';
import {Composition, Still} from 'remotion';
import {ShowcaseVideo} from './showcase-video';
import {ShowcasePoster} from './showcase-poster';

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="OhMyDynamicShowcase"
        component={ShowcaseVideo}
        durationInFrames={2250}
        fps={30}
        width={1920}
        height={1080}
      />
      <Still
        id="OhMyDynamicPoster"
        component={ShowcasePoster}
        width={1200}
        height={630}
      />
    </>
  );
};

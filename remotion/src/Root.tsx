import React from 'react';
import {Composition, Still, staticFile} from 'remotion';
import {Reel} from './Reel';
import {Thumbnail} from './Thumbnail';

// Les props reelles sont fournies au render via --props=props.json.
// calculateMetadata adapte dimensions/duree/fps a la video source.
const defaultProps = {
  video: 'cut.mp4',
  width: 1080,
  height: 1920,
  fps: 30,
  durationInFrames: 300,
  captions: [] as any[],
  zooms: [] as any[],
  sfx: [] as any[],
  config: {} as any,
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
    <Composition
      id="Reel"
      component={Reel as any}
      durationInFrames={defaultProps.durationInFrames}
      fps={defaultProps.fps}
      width={defaultProps.width}
      height={defaultProps.height}
      defaultProps={defaultProps}
      calculateMetadata={({props}) => {
        return {
          durationInFrames: Math.max(1, props.durationInFrames),
          fps: props.fps,
          width: props.width,
          height: props.height,
        };
      }}
    />
    <Still
      id="Thumb"
      component={Thumbnail as any}
      width={1280}
      height={720}
      defaultProps={{image: 'thumb_bg.jpg', title: 'TITRE *ICI*'}}
    />
  </>
  );
};

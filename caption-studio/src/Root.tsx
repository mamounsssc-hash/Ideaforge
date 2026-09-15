import React from "react";
import {Composition} from "remotion";
import {Captioned} from "./Captioned";
import input from "../input.json";

const FPS = 30;

// The clip is 9:16 (1080x1920). Duration comes from input.json so it matches
// the video length exactly (our Python app fills durationInSeconds).
export const RemotionRoot: React.FC = () => {
  const dur = Math.max(1, Math.round((input.durationInSeconds || 10) * FPS));
  return (
    <Composition
      id="Captioned"
      component={Captioned as unknown as React.FC}
      durationInFrames={dur}
      fps={FPS}
      width={1080}
      height={1920}
      defaultProps={input as never}
    />
  );
};

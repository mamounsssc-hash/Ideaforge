import React from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
} from "remotion";
import {loadFont as loadCairo} from "@remotion/google-fonts/Cairo";
import {loadFont as loadAnton} from "@remotion/google-fonts/Anton";

const cairo = loadCairo();
const anton = loadAnton();

type Word = {text: string; start: number; end: number};
type Style = {
  font?: "cairo" | "anton";
  primary?: string;      // normal word colour
  active?: string;       // the word being spoken now (or its box colour)
  activeText?: string;   // text colour when it sits on the box
  activeBox?: boolean;   // draw a coloured box behind the active word (Submagic look)
  keyword?: string;      // fixed colour for important words
  maxWords?: number;     // words visible at once
  uppercase?: boolean;
  fontSize?: number;     // px in the 1080-wide frame
  bottomPct?: number;    // distance from bottom, %
};
type Props = {
  video: string;
  durationInSeconds: number;
  words: Word[];
  keywords?: string[];
  style?: Style;
};

const norm = (s: string) =>
  s.toLowerCase().replace(/[^a-z0-9؀-ۿ]/g, "");

export const Captioned: React.FC<Props> = ({
  video,
  words,
  keywords = [],
  style = {},
}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const t = frame / fps;

  const maxWords = style.maxWords ?? 4;
  const primary = style.primary ?? "#FFFFFF";
  const active = style.active ?? "#FFD60A";
  const activeText = style.activeText ?? "#111111";
  const keyword = style.keyword ?? "#31E981";
  const fontFamily = style.font === "anton" ? anton.fontFamily : cairo.fontFamily;
  const fontSize = style.fontSize ?? Math.round(width * 0.075);
  const uppercase = style.uppercase ?? false;
  const bottomPct = style.bottomPct ?? 22;
  const kwset = new Set(keywords.map(norm));

  const Bg = () =>
    video ? (
      <OffthreadVideo
        src={staticFile(video)}
        style={{width: "100%", height: "100%", objectFit: "cover"}}
      />
    ) : (
      <AbsoluteFill style={{background: "#0e1116"}} />
    );

  // group words into caption lines
  const groups: Word[][] = [];
  for (let i = 0; i < words.length; i += maxWords) {
    groups.push(words.slice(i, i + maxWords));
  }

  // find the group + active word for the current time
  let g: Word[] | null = null;
  for (const grp of groups) {
    if (t >= grp[0].start - 0.05 && t <= grp[grp.length - 1].end + 0.25) {
      g = grp;
      break;
    }
  }
  if (!g) {
    return (
      <AbsoluteFill>
        <Bg />
      </AbsoluteFill>
    );
  }
  let ai = 0;
  for (let j = 0; j < g.length; j++) {
    if (t >= g[j].start - 0.02) ai = j;
  }
  const visible = g.slice(0, ai + 1); // progressive reveal — never show unsaid words

  return (
    <AbsoluteFill>
      <Bg />
      <AbsoluteFill
        style={{
          justifyContent: "flex-end",
          alignItems: "center",
          padding: `0 6% ${bottomPct}% 6%`,
        }}
      >
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            alignItems: "center",
            gap: "0.22em",
            fontFamily,
            fontWeight: 800,
            fontSize,
            lineHeight: 1.18,
            textAlign: "center",
          }}
        >
          {visible.map((w, j) => {
            const isActive = j === ai;
            const isKw = kwset.has(norm(w.text));
            const pop = spring({
              frame: frame - Math.round(w.start * fps),
              fps,
              config: {damping: 14, stiffness: 200, mass: 0.5},
            });
            const scale = isActive ? interpolate(pop, [0, 1], [0.82, 1]) : 1;
            const boxed = isActive && style.activeBox;
            const color = isActive
              ? boxed
                ? activeText
                : active
              : isKw
              ? keyword
              : primary;
            const txt = uppercase ? w.text.toUpperCase() : w.text;
            return (
              <span
                key={j}
                style={{
                  color,
                  background: boxed ? active : "transparent",
                  borderRadius: 16,
                  padding: boxed ? "0.02em 0.2em" : "0",
                  transform: `scale(${scale})`,
                  display: "inline-block",
                  WebkitTextStroke: boxed ? "0" : "2.2px #000",
                  textShadow: boxed ? "none" : "0 3px 9px rgba(0,0,0,.85)",
                }}
              >
                {txt}
              </span>
            );
          })}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

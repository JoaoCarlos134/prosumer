import { animate } from "framer-motion";
import { useEffect, useRef } from "react";

/** A sun whose rays turn and whose disc pulses about its own centre (cx, cy). The SVG transform attribute is set by
 * hand on every frame, with the centre written into it: CSS/framer transform origins on SVG and SMIL animations do not
 * behave the same in every browser (the rays drifted off the sun; the disc did not pulse in Chromium). */
export function Sun({ cx, cy, r, rays, rayFrom, rayLength, rayWidth, turn, pulse, scale = [0.94, 1.1], rayOpacity }: {
  cx: number;
  cy: number;
  r: number;
  rays: number;
  rayFrom: number; // distance from the centre to the ray's inner end
  rayLength: number;
  rayWidth: number;
  turn: number; // seconds per turn
  pulse: number; // seconds per pulse
  scale?: [number, number];
  rayOpacity?: (i: number) => number;
}) {
  const ring = useRef<SVGGElement>(null);
  const disc = useRef<SVGGElement>(null);
  useEffect(() => {
    const spin = animate(0, 360, { duration: turn, repeat: Infinity, ease: "linear", onUpdate: (a) => ring.current?.setAttribute("transform", `rotate(${a} ${cx} ${cy})`) });
    const beat = animate(scale[0], scale[1], { duration: pulse / 2, repeat: Infinity, repeatType: "mirror", ease: "easeInOut", onUpdate: (s: number) => disc.current?.setAttribute("transform", `translate(${cx} ${cy}) scale(${s})`) });
    return () => {
      spin.stop();
      beat.stop();
    };
  }, [cx, cy, turn, pulse, scale[0], scale[1]]);
  return (
    <>
      <g ref={ring}>
        {Array.from({ length: rays }, (_, i) => (
          <rect
            key={i}
            x={cx - rayWidth / 2}
            y={cy - rayFrom - rayLength}
            width={rayWidth}
            height={rayLength}
            rx={rayWidth / 2}
            fill="#F2B705"
            opacity={rayOpacity?.(i)}
            transform={`rotate(${(i * 360) / rays} ${cx} ${cy})`}
          />
        ))}
      </g>
      <g ref={disc} transform={`translate(${cx} ${cy})`}>
        <circle r={r} fill="#F2B705" />
      </g>
    </>
  );
}

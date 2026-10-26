import { animate, useReducedMotion } from "framer-motion";
import { useEffect, useRef, type ReactNode } from "react";

/** An SVG group that turns forever about (cx, cy) in the drawing's own coordinates, by setting the SVG
 * `rotate(angle cx cy)` attribute each frame. A CSS or Framer origin on SVG is measured from the group's box
 * (rays around a sun then orbit a point off the sun), and SMIL's animateTransform barely moved on this page in
 * Chrome (a rotation of a millionth of a degree). Still when the system asks for reduced motion. */
export function Spin({ cx, cy, seconds, children }: { cx: number; cy: number; seconds: number; children: ReactNode }) {
  const still = useReducedMotion();
  const g = useRef<SVGGElement>(null);
  useEffect(() => {
    if (still) return;
    const run = animate(0, 360, {
      duration: seconds,
      ease: "linear",
      repeat: Infinity,
      onUpdate: (a) => g.current?.setAttribute("transform", `rotate(${a} ${cx} ${cy})`),
    });
    return () => run.stop();
  }, [cx, cy, seconds, still]);
  return <g ref={g}>{children}</g>;
}

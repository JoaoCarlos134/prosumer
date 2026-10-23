import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import { useStore } from "../store";

/** The site on an OpenStreetMap map (the coordinates are the rounded ones, ~1 km), with a pulsing marker. */
export function SiteMap({ lat, lon, label, height = 260 }: { lat: number; lon: number; label: string; height?: number | string }) {
  const box = useRef<HTMLDivElement>(null);
  const theme = useStore((s) => s.theme);
  useEffect(() => {
    const map = L.map(box.current!, { zoomControl: true, attributionControl: true, scrollWheelZoom: false }).setView([lat, lon], 11);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 15,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      className: theme === "dark" ? "map-dark" : "",
    }).addTo(map);
    const icon = L.divIcon({ className: "", html: '<span class="site-pin"><span></span></span>', iconSize: [22, 22], iconAnchor: [11, 11] });
    L.marker([lat, lon], { icon }).addTo(map).bindTooltip(label, { direction: "top", offset: [0, -10] });
    L.circle([lat, lon], { radius: 1000, color: "#118DFF", weight: 1, fillOpacity: 0.06, dashArray: "4 4" }).addTo(map);
    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(box.current!);
    return () => {
      ro.disconnect();
      map.remove();
    };
  }, [lat, lon, label, theme]);
  return <div ref={box} className="overflow-hidden rounded-[2px]" style={{ height, width: "100%" }} />;
}

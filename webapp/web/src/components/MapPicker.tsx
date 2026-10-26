import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { LocateFixed, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useStore, useT } from "../store";

/** Pick the site on an OpenStreetMap map: a click (or dragging the pin) sets the latitude and longitude; "use my
 * location" asks the browser. Nothing leaves the computer here but the map tiles of the view (the library
 * rounds the site to ~1 km before any download). */
export function MapPicker({ height = 220 }: { height?: number | string }) {
  const t = useT();
  const theme = useStore((s) => s.theme);
  const form = useStore((s) => s.form);
  const setForm = useStore((s) => s.setForm);
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const pin = useRef<L.Marker | null>(null);
  const [locating, setLocating] = useState(false);
  const [denied, setDenied] = useState(false);

  const lat = Number(form.latitude.replace(",", "."));
  const lon = Number(form.longitude.replace(",", "."));
  const known = form.latitude.trim() !== "" && form.longitude.trim() !== "" && Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180;

  const put = (la: number, lo: number) => setForm({ where: "coords", latitude: la.toFixed(4), longitude: lo.toFixed(4) });

  useEffect(() => {
    const m = L.map(box.current!, { zoomControl: true, attributionControl: true, scrollWheelZoom: true, worldCopyJump: true });
    m.setView(known ? [lat, lon] : [10, 0], known ? 11 : 2);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 17,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      className: theme === "dark" ? "map-dark" : "",
    }).addTo(m);
    m.on("click", (e: L.LeafletMouseEvent) => put(e.latlng.lat, e.latlng.lng));
    map.current = m;
    const ro = new ResizeObserver(() => m.invalidateSize());
    ro.observe(box.current!);
    return () => {
      ro.disconnect();
      m.remove();
      map.current = null;
      pin.current = null;
    };
    // made once per theme; the pin follows the typed coordinates below
  }, [theme]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    if (!known) {
      pin.current?.remove();
      pin.current = null;
      return;
    }
    if (!pin.current) {
      const icon = L.divIcon({ className: "", html: '<span class="site-pin"><span></span></span>', iconSize: [22, 22], iconAnchor: [11, 11] });
      pin.current = L.marker([lat, lon], { icon, draggable: true }).addTo(m);
      pin.current.on("dragend", () => {
        const p = pin.current!.getLatLng();
        put(p.lat, p.lng);
      });
      m.setView([lat, lon], Math.max(m.getZoom(), 11), { animate: true });
    } else {
      pin.current.setLatLng([lat, lon]);
      if (!m.getBounds().contains([lat, lon])) m.panTo([lat, lon]);
    }
  }, [known, lat, lon]);

  const locate = () => {
    if (!navigator.geolocation) return setDenied(true);
    setLocating(true);
    setDenied(false);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setLocating(false);
        put(p.coords.latitude, p.coords.longitude);
        map.current?.setView([p.coords.latitude, p.coords.longitude], 13, { animate: true });
      },
      () => {
        setLocating(false);
        setDenied(true);
      },
      { enableHighAccuracy: false, timeout: 10000 },
    );
  };

  return (
    <div className="space-y-1.5">
      <div className="relative">
        <div ref={box} className="isolate z-0 overflow-hidden rounded-xl border border-line" style={{ height, width: "100%" }} />
        <button
          type="button"
          onClick={locate}
          className="absolute right-2 top-2 z-[500] flex items-center gap-1.5 rounded-lg border border-line bg-surface/95 px-2 py-1 text-[11.5px] font-semibold text-ink shadow-md backdrop-blur transition hover:bg-hover"
        >
          {locating ? <Loader2 size={13} className="animate-spin" /> : <LocateFixed size={13} className="text-[#118DFF]" />}
          {t("useMyLocation")}
        </button>
      </div>
      <p className={`text-[10.5px] leading-snug ${denied ? "text-[#D64550]" : "text-muted"}`}>{denied ? t("locationDenied") : t("pickOnMap")}</p>
    </div>
  );
}

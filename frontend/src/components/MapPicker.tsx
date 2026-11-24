"use client";

import L from "leaflet";
import { Circle, MapContainer, Marker, TileLayer, Tooltip, useMapEvents } from "react-leaflet";
import type { ScanSummary } from "@/lib/api";

export interface PickedLocation {
  lat: number;
  lng: number;
}

// Pin görselleri public/leaflet/ altından servis edilir (bundler importu yerine
// sabit URL — Turbopack'te görsel importları düz string döner).
const pin = L.icon({
  iconUrl: "/leaflet/marker-icon.png",
  iconRetinaUrl: "/leaflet/marker-icon-2x.png",
  shadowUrl: "/leaflet/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

const DEFAULT_CENTER: [number, number] = [39.9255, 32.8663]; // Ankara

function ClickCatcher({ onPick }: { onPick: (p: PickedLocation) => void }) {
  useMapEvents({
    click: (e) => onPick({ lat: e.latlng.lat, lng: e.latlng.lng }),
  });
  return null;
}

function scanLabel(s: ScanSummary): string {
  const d = new Date(s.scanned_at).toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
  return `${d} · ${s.stats.shown} aday`;
}

export default function MapPicker({ value, radius, scans, onPick }: {
  value: PickedLocation | null;
  radius: number;
  scans: ScanSummary[];
  onPick: (p: PickedLocation) => void;
}) {
  return (
    <MapContainer
      center={value ? [value.lat, value.lng] : DEFAULT_CENTER}
      zoom={13}
      className="h-full w-full rounded-xl"
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> katkıcıları'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ClickCatcher onPick={onPick} />
      {scans.map((s) => (
        <Circle
          key={s.id}
          center={[s.lat, s.lng]}
          radius={s.radius_m}
          pathOptions={{ color: "#0f766e", weight: 1.5, dashArray: "6 6", fillOpacity: 0.06 }}
        >
          <Tooltip>{scanLabel(s)}</Tooltip>
        </Circle>
      ))}
      {value && (
        <>
          <Marker
            position={[value.lat, value.lng]}
            icon={pin}
            draggable
            eventHandlers={{ dragend: (e) => {
              const ll = (e.target as L.Marker).getLatLng();
              onPick({ lat: ll.lat, lng: ll.lng });
            } }}
          />
          <Circle
            center={[value.lat, value.lng]}
            radius={radius}
            pathOptions={{ color: "#24589a", weight: 1.5, fillOpacity: 0.08 }}
          />
        </>
      )}
    </MapContainer>
  );
}

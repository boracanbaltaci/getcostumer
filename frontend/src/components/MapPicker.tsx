"use client";

import L from "leaflet";
import { Circle, MapContainer, Marker, TileLayer, useMapEvents } from "react-leaflet";

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

export default function MapPicker({ value, radius, onPick }: {
  value: PickedLocation | null;
  radius: number;
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
